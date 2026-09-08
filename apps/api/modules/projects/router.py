from fastapi import APIRouter, Cookie, Depends, HTTPException, Query

from apps.api.core.rate_limit import RateLimitExceededError, check_rate_limit
from apps.api.modules.authz import service as authz_service
from apps.api.modules.identity import service as identity_service
from apps.api.modules.licensing.service import require_valid_license
from apps.api.modules.projects import service as projects_service
from apps.api.modules.projects.schemas import (
    LinkOut,
    ProjectDetailOut,
    ProjectOut,
    ProjectRequestCreate,
    ProjectRequestOut,
    ProjectUpdate,
)
from apps.api.modules.projects.service import ProjectApprovalError, ProjectValidationError
from apps.api.modules.projects.tasks import assess_project_request
from apps.api.modules.tools import service as tools_service
from apps.api.modules.vendors import service as vendors_service

router = APIRouter(prefix="/projects", tags=["projects"], dependencies=[Depends(require_valid_license)])


def _require_user(session_token: str | None):
    user = identity_service.get_current_user(session_token)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def _tool_links_out(org, links) -> list[LinkOut]:
    tools_by_id = {str(t.id): t for t in tools_service.list_approved_tools(org)}
    out = []
    for link in links:
        tool = tools_by_id.get(str(link.tool_id)) if link.tool_id else None
        out.append(
            LinkOut(
                id=str(link.id),
                tool_id=str(link.tool_id) if link.tool_id else None,
                other_name=link.other_name,
                name=tool.name if tool else link.other_name,
                status=None,
                in_inventory=tool is not None,
            )
        )
    return out


def _vendor_links_out(org, links) -> list[LinkOut]:
    vendors_by_id = {str(v.id): v for v in vendors_service.list_vendors(org)}
    out = []
    for link in links:
        vendor = vendors_by_id.get(str(link.vendor_id)) if link.vendor_id else None
        out.append(
            LinkOut(
                id=str(link.id),
                vendor_id=str(link.vendor_id) if link.vendor_id else None,
                other_name=link.other_name,
                name=vendor.name if vendor else link.other_name,
                status=vendor.status if vendor else None,
                in_inventory=vendor is not None,
            )
        )
    return out


def _to_project_out(project) -> ProjectOut:
    return ProjectOut(
        id=str(project.id),
        name=project.name,
        description=project.description,
        lifecycle_stage=project.lifecycle_stage,
        owner_user_id=str(project.owner_user_id) if project.owner_user_id else None,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def _to_request_out(org, request) -> ProjectRequestOut:
    requester = identity_service.get_user_by_id(org, request.requested_by)
    tool_links = projects_service.get_request_tool_links(org, str(request.id))
    vendor_links = projects_service.get_request_vendor_links(org, str(request.id))
    return ProjectRequestOut(
        id=str(request.id),
        name=request.name,
        description=request.description,
        business_justification=request.business_justification,
        data_flow_description=request.data_flow_description,
        data_tiers=request.data_tiers,
        human_in_loop=request.human_in_loop,
        status=request.status,
        project_assessment_status=request.project_assessment_status,
        project_assessment_result=request.project_assessment_result,
        project_assessment_explanation=request.project_assessment_explanation,
        requested_by=str(request.requested_by),
        requested_by_email=requester.email if requester else None,
        decided_by=str(request.decided_by) if request.decided_by else None,
        decided_at=request.decided_at,
        resulting_project_id=str(request.resulting_project_id) if request.resulting_project_id else None,
        created_at=request.created_at,
        updated_at=request.updated_at,
        linked_tools=_tool_links_out(org, tool_links),
        linked_vendors=_vendor_links_out(org, vendor_links),
    )


@router.post("/request", response_model=ProjectRequestOut)
def create_project_request(body: ProjectRequestCreate, misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "project.request"):
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        # Every request that isn't skipped fires a real (billed, once
        # AI_PROVIDER=live) LLM call via the Celery task below - same
        # per-user spend/abuse bound as tools/router.py::create_tool_request.
        check_rate_limit(f"project-request:{user.id}", limit=20, window_seconds=3600)
    except RateLimitExceededError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    org = identity_service.get_org()
    try:
        request = projects_service.create_project_request(
            org,
            user,
            body.name,
            body.description,
            body.business_justification,
            body.data_flow_description,
            body.human_in_loop,
            [link.model_dump() for link in body.tool_links],
            [link.model_dump() for link in body.vendor_links],
            data_tiers=body.data_tiers,
        )
    except ProjectValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if request.project_assessment_status == "pending":
        assess_project_request.delay(str(request.id), str(org.id))
    return _to_request_out(org, request)


@router.get("/requests", response_model=list[ProjectRequestOut])
def list_project_requests(mine: bool = Query(default=False), misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    org = identity_service.get_org()
    if mine:
        requests = projects_service.list_project_requests(org, mine=user)
    else:
        if not authz_service.can(user, "project.approve"):
            raise HTTPException(status_code=403, detail="Forbidden")
        requests = projects_service.list_project_requests(org, pending_only=True)
    return [_to_request_out(org, r) for r in requests]


@router.post("/requests/{request_id}/approve", response_model=ProjectRequestOut)
def approve_project_request(request_id: str, misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "project.approve"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    try:
        request = projects_service.approve_project_request(org, request_id, user)
    except ProjectApprovalError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_request_out(org, request)


@router.post("/requests/{request_id}/reject", response_model=ProjectRequestOut)
def reject_project_request(request_id: str, misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "project.approve"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    try:
        request = projects_service.reject_project_request(org, request_id, user)
    except ProjectApprovalError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_request_out(org, request)


@router.get("", response_model=list[ProjectOut])
def list_projects(misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "project.view"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    return [_to_project_out(p) for p in projects_service.list_projects(org)]


@router.get("/{project_id}", response_model=ProjectDetailOut)
def get_project(project_id: str, misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "project.view"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    project = projects_service.get_project(org, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    base = _to_project_out(project)
    tool_links = projects_service.get_project_tool_links(org, project_id)
    vendor_links = projects_service.get_project_vendor_links(org, project_id)
    return ProjectDetailOut(
        **base.model_dump(),
        linked_tools=_tool_links_out(org, tool_links),
        linked_vendors=_vendor_links_out(org, vendor_links),
    )


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(project_id: str, body: ProjectUpdate, misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "project.manage"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    try:
        project = projects_service.update_project(
            org, project_id, name=body.name, description=body.description, lifecycle_stage=body.lifecycle_stage
        )
    except ProjectValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return _to_project_out(project)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "project.manage"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    deleted = projects_service.delete_project(org, project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")
