from fastapi import APIRouter, Cookie, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response

from apps.api.core.media import LogoValidationError, validate_logo_upload
from apps.api.core.rate_limit import RateLimitExceededError, check_rate_limit
from apps.api.modules.authz import service as authz_service
from apps.api.modules.identity import service as identity_service
from apps.api.modules.licensing.service import require_valid_license
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

router = APIRouter(prefix="/tools", tags=["tools"], dependencies=[Depends(require_valid_license)])


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
        logo_url=tool.logo_url,
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
        data_tiers=request.data_tiers,
        requires_enterprise_account=request.requires_enterprise_account,
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
            logo_url=body.logo_url,
        )
    except ToolApprovalError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")
    return _to_approved_tool_out(tool)


@router.post("/approved/{tool_id}/logo", response_model=ApprovedToolOut)
async def upload_tool_logo(tool_id: str, file: UploadFile = File(...), misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "tools.manage"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    data = await file.read()
    try:
        content_type = validate_logo_upload(file.content_type, data)
    except LogoValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    tool = tools_service.upload_tool_logo(org, tool_id, content_type, data)
    if tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")
    return _to_approved_tool_out(tool)


@router.get("/approved/{tool_id}/logo-file")
def get_tool_logo(tool_id: str):
    """Deliberately unauthenticated (unlike every other route on this
    router) - a browser <img> tag loading this cross-origin (API on a
    different port than the frontend) won't send the httponly session
    cookie without crossOrigin="use-credentials" wired up on the <img>
    element, and a logo is branding-adjacent, non-sensitive imagery, not
    data worth gating behind a session the way the catalog data itself
    is (same posture as the already-public GET /branding/config)."""
    org = identity_service.get_org()
    result = tools_service.get_tool_logo_bytes(org, tool_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Logo not found")
    data, content_type = result
    return Response(content=data, media_type=content_type)


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
    try:
        # Every request that isn't skipped fires a real (billed, once
        # AI_PROVIDER=live) LLM call via the Celery task below - this
        # bounds per-user spend/abuse, not general API traffic.
        check_rate_limit(f"tool-request:{user.id}", limit=20, window_seconds=3600)
    except RateLimitExceededError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    org = identity_service.get_org()
    try:
        request = tools_service.create_request(
            org,
            user,
            body.request_type,
            body.name,
            body.link,
            body.intended_use_case,
            data_tiers=body.data_tiers,
            requires_enterprise_account=body.requires_enterprise_account,
        )
    except ToolRequestDuplicateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ToolRequestValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if request.ai_assessment_status == "pending":
        # create_request() already sets ai_assessment_status="skipped"
        # directly (no active policy to assess against) instead of
        # leaving it "pending" - only enqueue the task when there's
        # actually something for it to do.
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
