import json
import uuid

from apps.api.core.celery_app import celery_app
from apps.api.core.db import SessionLocal, org_scoped_session
from apps.api.modules.ai_gateway import service as ai_gateway_service
from apps.api.modules.identity.models import Org
from apps.api.modules.policy import service as policy_service
from apps.api.modules.tools.models import ToolRequest
from apps.api.modules.tools.prompts import TOOL_ASSESSMENT_SYSTEM_PROMPT, build_assessment_prompt

VALID_CLASSIFICATIONS = {"approvable", "needs_review", "cannot_approve"}


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
        prompt = build_assessment_prompt(policy_text, request_type, name, link, use_case)
        result = ai_gateway_service.complete("tool_assessment", org, prompt, system=TOOL_ASSESSMENT_SYSTEM_PROMPT)
        parsed = json.loads(result.content)
        classification = parsed.get("classification")
        explanation = parsed.get("explanation")
        if classification not in VALID_CLASSIFICATIONS or not explanation:
            raise ValueError(f"Unexpected assessment response shape: {parsed!r}")

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
