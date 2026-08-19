from fastapi import APIRouter, Cookie, HTTPException, Query

from apps.api.modules.authz import service as authz_service
from apps.api.modules.identity import service as identity_service
from apps.api.modules.tools import service as tools_service
from apps.api.modules.tools.schemas import (
    ApprovedToolOut,
    ApprovedToolUpdate,
    ToolRequestApprove,
    ToolRequestCreate,
    ToolRequestOut,
    ToolRequestReject,
)
from apps.api.modules.tools.service import (
    ToolApprovalError,
    ToolRequestDuplicateError,
    ToolRequestValidationError,
)
from apps.api.modules.tools.tasks import assess_tool_request

router = APIRouter(prefix="/tools", tags=["tools"])


def _require_user(session_token: str | None):
    user = identity_service.get_current_user(session_token)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def _to_approved_tool_out(tool) -> ApprovedToolOut:
    return ApprovedToolOut(
        id=str(tool.id),
        name=tool.name,
        description=tool.description,
        source_type=tool.source_type,
        access_url=tool.access_url,
        allowed_tiers=tool.allowed_tiers,
        details=tool.details,
        created_at=tool.created_at,
    )


def _to_tool_request_out(org, request) -> ToolRequestOut:
    requester = identity_service.get_user_by_id(org, request.requested_by)
    return ToolRequestOut(
        id=str(request.id),
        request_type=request.request_type,
        name=request.name,
        link=request.link,
        intended_use_case=request.intended_use_case,
        status=request.status,
        ai_assessment_status=request.ai_assessment_status,
        ai_assessment_result=request.ai_assessment_result,
        ai_assessment_explanation=request.ai_assessment_explanation,
        requested_by=str(request.requested_by),
        requested_by_email=requester.email if requester else None,
        decided_by=str(request.decided_by) if request.decided_by else None,
        decided_at=request.decided_at,
        decision_note=request.decision_note,
        resulting_tool_id=str(request.resulting_tool_id) if request.resulting_tool_id else None,
        created_at=request.created_at,
        updated_at=request.updated_at,
    )


@router.get("/approved", response_model=list[ApprovedToolOut])
def list_approved_tools(misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "tools.view"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    return [_to_approved_tool_out(t) for t in tools_service.list_approved_tools(org)]


@router.patch("/approved/{tool_id}", response_model=ApprovedToolOut)
def update_approved_tool(tool_id: str, body: ApprovedToolUpdate, misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "tools.manage"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    try:
        tool = tools_service.update_approved_tool(
            org,
            tool_id,
            name=body.name,
            description=body.description,
            access_url=body.access_url,
            allowed_tiers=body.allowed_tiers,
        )
    except ToolApprovalError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")
    return _to_approved_tool_out(tool)


@router.delete("/approved/{tool_id}", status_code=204)
def delete_approved_tool(tool_id: str, misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "tools.manage"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    deleted = tools_service.delete_approved_tool(org, tool_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Tool not found")


@router.post("/requests", response_model=ToolRequestOut)
def create_tool_request(body: ToolRequestCreate, misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "tools.request"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    try:
        request = tools_service.create_request(org, user, body.request_type, body.name, body.link, body.intended_use_case)
    except ToolRequestDuplicateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ToolRequestValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    assess_tool_request.delay(str(request.id), str(org.id))
    return _to_tool_request_out(org, request)


@router.get("/requests", response_model=list[ToolRequestOut])
def list_tool_requests(mine: bool = Query(default=False), misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    org = identity_service.get_org()
    if mine:
        requests = tools_service.list_requests(org, mine=user)
    else:
        if not authz_service.can(user, "tools.approve"):
            raise HTTPException(status_code=403, detail="Forbidden")
        requests = tools_service.list_requests(org, pending_only=True)
    return [_to_tool_request_out(org, r) for r in requests]


@router.post("/requests/{request_id}/approve", response_model=ToolRequestOut)
def approve_tool_request(request_id: str, body: ToolRequestApprove, misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "tools.approve"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    try:
        request = tools_service.approve_request(
            org, request_id, user, description=body.description, allowed_tiers=body.allowed_tiers
        )
    except ToolApprovalError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_tool_request_out(org, request)


@router.post("/requests/{request_id}/reject", response_model=ToolRequestOut)
def reject_tool_request(request_id: str, body: ToolRequestReject, misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "tools.approve"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    try:
        request = tools_service.reject_request(org, request_id, user, reason=body.reason)
    except ToolApprovalError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_tool_request_out(org, request)
