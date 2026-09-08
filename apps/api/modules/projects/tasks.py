import json
import re
import uuid

from apps.api.core.celery_app import celery_app
from apps.api.core.db import SessionLocal, org_scoped_session
from apps.api.modules.ai_gateway import service as ai_gateway_service
from apps.api.modules.identity.models import Org
from apps.api.modules.policy import service as policy_service
from apps.api.modules.projects.models import ProjectRequest
from apps.api.modules.projects.prompts import render_assessment_prompt
from apps.api.modules.projects.service import get_request_tool_links, get_request_vendor_links
from apps.api.modules.tools import service as tools_service
from apps.api.modules.vendors import service as vendors_service

# Direct copy of tools/tasks.py's classification-normalization contract -
# an admin-edited prompt or ordinary model drift shouldn't be able to
# break parsing.
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


def _parse_project_assessment(raw: str) -> tuple[str, str]:
    """Never returns a classification the caller could mistake for success
    without both a valid classification and a non-empty rationale - any
    other shape raises, and the caller's except-block turns that into
    project_assessment_status="failed" (never an assumed approval)."""
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
    db = SessionLocal()
    try:
        return db.get(Org, uuid.UUID(org_id))
    finally:
        db.close()


def _linked_names(org, tool_links, vendor_links) -> tuple[list[tuple[str, bool]], list[tuple[str, bool]]]:
    tools_by_id = {str(t.id): t for t in tools_service.list_approved_tools(org)}
    vendors_by_id = {str(v.id): v for v in vendors_service.list_vendors(org)}
    linked_tools = [
        (tools_by_id[str(link.tool_id)].name, True) if link.tool_id else (link.other_name or "", False)
        for link in tool_links
    ]
    linked_vendors = [
        (vendors_by_id[str(link.vendor_id)].name, True) if link.vendor_id else (link.other_name or "", False)
        for link in vendor_links
    ]
    return linked_tools, linked_vendors


@celery_app.task(name="projects.assess_project_request")
def assess_project_request(request_id: str, org_id: str) -> None:
    """Direct structural copy of tools/tasks.py::assess_tool_request() -
    same Celery-task-only rule, same fail-safe (never sets
    project_assessment_result on any failure path, only
    project_assessment_status="failed")."""
    org = _load_org(org_id)
    if org is None:
        return

    with org_scoped_session(str(org.id)) as db:
        request = db.get(ProjectRequest, uuid.UUID(request_id))
        if request is None:
            return
        name = request.name
        description = request.description
        business_justification = request.business_justification
        data_flow_description = request.data_flow_description
        data_tiers = request.data_tiers
        human_in_loop = request.human_in_loop

    try:
        policy_text = policy_service.get_active_policy_text(org)
        if not policy_text:
            raise ValueError("No active AI Policy text available for assessment")

        tool_links = get_request_tool_links(org, request_id)
        vendor_links = get_request_vendor_links(org, request_id)
        linked_tools, linked_vendors = _linked_names(org, tool_links, vendor_links)

        prompt = render_assessment_prompt(
            org, name, description, business_justification, data_flow_description, human_in_loop,
            linked_tools, linked_vendors, policy_text, data_tiers=data_tiers,
        )
        result = ai_gateway_service.complete("project_assessment", org, prompt)
        classification, explanation = _parse_project_assessment(result.content)

        with org_scoped_session(str(org.id)) as db:
            target = db.get(ProjectRequest, uuid.UUID(request_id))
            if target is not None:
                target.project_assessment_status = "complete"
                target.project_assessment_result = classification
                target.project_assessment_explanation = explanation
    except Exception as exc:  # noqa: BLE001 - any failure must land on "failed", never silently "approvable"
        with org_scoped_session(str(org.id)) as db:
            target = db.get(ProjectRequest, uuid.UUID(request_id))
            if target is not None:
                target.project_assessment_status = "failed"
                target.project_assessment_explanation = f"AI assessment could not be completed: {exc}"[:500]
