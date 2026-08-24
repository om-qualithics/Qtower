import json
import re
import uuid

from apps.api.core.celery_app import celery_app
from apps.api.core.db import SessionLocal, org_scoped_session
from apps.api.modules.ai_gateway import service as ai_gateway_service
from apps.api.modules.identity.models import Org
from apps.api.modules.policy import service as policy_service
from apps.api.modules.tools.models import ToolRequest
from apps.api.modules.tools.prompts import render_assessment_prompt

# Maps every label variant the (admin-editable) prompt might come back
# with onto this app's internal enum values - case-insensitive, since an
# admin-edited prompt or ordinary model drift shouldn't be able to break
# parsing. The prompt's own instructed labels are "Approvable"/"Need
# Review"/"Unapprovable"; a few synonyms are accepted defensively.
_CLASSIFICATION_MAP = {
    "approvable": "approvable",
    "need review": "needs_review",
    "needs review": "needs_review",
    "needs_review": "needs_review",
    "unapprovable": "cannot_approve",
    "cannot approve": "cannot_approve",
    "cannot_approve": "cannot_approve",
    "not approvable": "cannot_approve",
}
_CLASSIFICATION_KEYS = ("classification", "request_classification")
_RATIONALE_KEYS = ("rational", "rationale", "explanation", "classification_rational")
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_assessment(raw: str) -> tuple[str, str]:
    """Never raises a classification the caller could mistake for success
    without both a valid classification and a non-empty rationale - any
    other shape raises, and the caller's except-block turns that into
    ai_assessment_status="failed" (never an assumed approval)."""
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        match = _JSON_OBJECT_RE.search(raw)
        if not match:
            raise ValueError(f"No JSON object found in assessment response: {raw!r}") from None
        parsed = json.loads(match.group(0))

    classification_raw = next((parsed[k] for k in _CLASSIFICATION_KEYS if parsed.get(k)), "")
    classification = _CLASSIFICATION_MAP.get(str(classification_raw).strip().lower())
    rationale = next((parsed[k] for k in _RATIONALE_KEYS if parsed.get(k)), None)
    if not classification or not rationale:
        raise ValueError(f"Unexpected assessment response shape: {parsed!r}")
    return classification, rationale


def _load_org(org_id: str) -> Org | None:
    """Loads by id rather than identity_service.get_org() (which just picks
    "the" org, v1's single-org-per-container assumption) - the task is
    handed a specific org_id by the router and must act on exactly that
    org, not whichever one happens to be first in the table."""
    db = SessionLocal()
    try:
        return db.get(Org, uuid.UUID(org_id))
    finally:
        db.close()


@celery_app.task(name="tools.assess_tool_request")
def assess_tool_request(request_id: str, org_id: str) -> None:
    """The first real caller of ai_gateway.complete() (Milestone 4's
    "Celery-task-only" rule) - never invoked synchronously from a route.
    Never sets ai_assessment_result on any failure path (bad JSON, gateway
    error, missing policy) - only ai_assessment_status="failed" - so a
    broken assessment can never be mistaken for "approvable" (handoff: AI
    never automatically approves)."""
    org = _load_org(org_id)
    if org is None:
        return

    with org_scoped_session(str(org.id)) as db:
        request = db.get(ToolRequest, uuid.UUID(request_id))
        if request is None:
            return
        request_type = request.request_type
        name = request.name
        link = request.link
        use_case = request.intended_use_case

    try:
        policy_text = policy_service.get_active_policy_text(org)
        if not policy_text:
            # Should not normally happen - the router only enqueues this
            # task when create_request() already confirmed an active
            # policy exists - but the policy could in principle have been
            # archived in the gap between request creation and this task
            # running. Fail closed, same as any other assessment failure.
            raise ValueError("No active AI Policy text available for assessment")
        prompt = render_assessment_prompt(org, request_type, name, link, use_case, policy_text)
        result = ai_gateway_service.complete("tool_assessment", org, prompt)
        classification, explanation = _parse_assessment(result.content)

        with org_scoped_session(str(org.id)) as db:
            target = db.get(ToolRequest, uuid.UUID(request_id))
            if target is not None:
                target.ai_assessment_status = "complete"
                target.ai_assessment_result = classification
                target.ai_assessment_explanation = explanation
    except Exception as exc:  # noqa: BLE001 - any failure must land on "failed", never silently "approvable"
        with org_scoped_session(str(org.id)) as db:
            target = db.get(ToolRequest, uuid.UUID(request_id))
            if target is not None:
                target.ai_assessment_status = "failed"
                target.ai_assessment_explanation = f"AI assessment could not be completed: {exc}"[:500]
