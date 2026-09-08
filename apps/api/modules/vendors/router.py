from fastapi import APIRouter, Cookie, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response

from apps.api.core.media import LogoValidationError, validate_logo_upload
from apps.api.modules.authz import service as authz_service
from apps.api.modules.identity import service as identity_service
from apps.api.modules.licensing.service import require_valid_license
from apps.api.modules.vendors import service as vendors_service
from apps.api.modules.vendors.schemas import (
    ChecklistResponsesUpdate,
    VendorChecklistItemOut,
    VendorDetailOut,
    VendorLogoUrlUpdate,
    VendorOut,
    VendorRequestCreate,
    VendorRequestOut,
)
from apps.api.modules.vendors.service import VendorApprovalError, VendorRequestDuplicateError, VendorValidationError

router = APIRouter(prefix="/vendors", tags=["vendors"], dependencies=[Depends(require_valid_license)])


def _require_user(session_token: str | None):
    user = identity_service.get_current_user(session_token)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def _to_vendor_out(vendor) -> VendorOut:
    return VendorOut(
        id=str(vendor.id),
        name=vendor.name,
        type=vendor.type,
        category=vendor.category,
        logo_url=vendor.logo_url,
        website_url=vendor.website_url,
        status=vendor.status,
        overall_score=float(vendor.overall_score) if vendor.overall_score is not None else None,
        created_at=vendor.created_at,
    )


def _to_vendor_request_out(org, request) -> VendorRequestOut:
    requester = identity_service.get_user_by_id(org, request.requested_by)
    responses = vendors_service.get_vendor_request_responses(org, str(request.id))
    return VendorRequestOut(
        id=str(request.id),
        name=request.name,
        type=request.type,
        website_url=request.website_url,
        business_justification=request.business_justification,
        projected_status=request.projected_status,
        overall_score=float(request.overall_score) if request.overall_score is not None else None,
        status=request.status,
        requested_by=str(request.requested_by),
        requested_by_email=requester.email if requester else None,
        decided_by=str(request.decided_by) if request.decided_by else None,
        decided_at=request.decided_at,
        resulting_vendor_id=str(request.resulting_vendor_id) if request.resulting_vendor_id else None,
        created_at=request.created_at,
        checklist_responses=[
            {"checklist_item_id": str(r.checklist_item_id), "answer": r.answer, "evidence_note": r.evidence_note}
            for r in responses
        ],
    )


@router.get("/checklist-items", response_model=list[VendorChecklistItemOut])
def list_checklist_items(
    applies_to: str | None = Query(default=None), misty_session: str | None = Cookie(default=None)
):
    user = _require_user(misty_session)
    if not authz_service.can(user, "vendor.view"):
        raise HTTPException(status_code=403, detail="Forbidden")
    items = vendors_service.list_checklist_items(applies_to)
    return [
        VendorChecklistItemOut(
            id=str(i.id), key=i.key, question=i.question, tier=i.tier, applies_to=i.applies_to, sort_order=i.sort_order
        )
        for i in items
    ]


@router.post("/request", response_model=VendorRequestOut)
def create_vendor_request(body: VendorRequestCreate, misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "vendor.request"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    try:
        request = vendors_service.create_vendor_request(
            org,
            user,
            body.name,
            body.type,
            body.website_url,
            body.business_justification,
            [r.model_dump() for r in body.responses],
        )
    except VendorRequestDuplicateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except VendorValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_vendor_request_out(org, request)


@router.get("/requests", response_model=list[VendorRequestOut])
def list_vendor_requests(mine: bool = Query(default=False), misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    org = identity_service.get_org()
    if mine:
        requests = vendors_service.list_vendor_requests(org, mine=user)
    else:
        if not authz_service.can(user, "vendor.approve"):
            raise HTTPException(status_code=403, detail="Forbidden")
        requests = vendors_service.list_vendor_requests(org, pending_only=True)
    return [_to_vendor_request_out(org, r) for r in requests]


@router.post("/requests/{request_id}/approve", response_model=VendorRequestOut)
def approve_vendor_request(request_id: str, misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "vendor.approve"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    try:
        request = vendors_service.approve_vendor_request(org, request_id, user)
    except VendorApprovalError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_vendor_request_out(org, request)


@router.post("/requests/{request_id}/reject", response_model=VendorRequestOut)
def reject_vendor_request(request_id: str, misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "vendor.approve"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    try:
        request = vendors_service.reject_vendor_request(org, request_id, user)
    except VendorApprovalError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_vendor_request_out(org, request)


@router.get("", response_model=list[VendorOut])
def list_vendors(type: str | None = Query(default=None), misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "vendor.view"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    return [_to_vendor_out(v) for v in vendors_service.list_vendors(org, type_=type)]


@router.get("/{vendor_id}", response_model=VendorDetailOut)
def get_vendor(vendor_id: str, misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "vendor.view"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    vendor = vendors_service.get_vendor(org, vendor_id)
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")
    responses = vendors_service.get_vendor_responses(org, vendor_id)
    base = _to_vendor_out(vendor)
    return VendorDetailOut(
        **base.model_dump(),
        checklist_responses=[
            {
                "checklist_item_id": str(r.checklist_item_id),
                "answer": r.answer,
                "evidence_note": r.evidence_note,
                "last_verified_date": r.last_verified_date,
            }
            for r in responses
        ],
    )


@router.put("/{vendor_id}/checklist-responses", response_model=VendorOut)
def update_checklist_responses(
    vendor_id: str, body: ChecklistResponsesUpdate, misty_session: str | None = Cookie(default=None)
):
    user = _require_user(misty_session)
    if not authz_service.can(user, "vendor.manage"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    try:
        vendor = vendors_service.update_checklist_responses(
            org, vendor_id, [r.model_dump() for r in body.responses]
        )
    except VendorValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return _to_vendor_out(vendor)


@router.patch("/{vendor_id}/logo", response_model=VendorOut)
def update_vendor_logo_url(vendor_id: str, body: VendorLogoUrlUpdate, misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "vendor.manage"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    vendor = vendors_service.update_vendor_logo_url(org, vendor_id, body.logo_url)
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return _to_vendor_out(vendor)


@router.post("/{vendor_id}/logo", response_model=VendorOut)
async def upload_vendor_logo(vendor_id: str, file: UploadFile = File(...), misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "vendor.manage"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    data = await file.read()
    try:
        content_type = validate_logo_upload(file.content_type, data)
    except LogoValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    vendor = vendors_service.upload_vendor_logo(org, vendor_id, content_type, data)
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return _to_vendor_out(vendor)


@router.get("/{vendor_id}/logo-file")
def get_vendor_logo(vendor_id: str):
    """Deliberately unauthenticated - see tools/router.py::get_tool_logo()'s
    docstring for the full reasoning (cross-origin <img> cookie limits,
    non-sensitive branding-adjacent imagery)."""
    org = identity_service.get_org()
    result = vendors_service.get_vendor_logo_bytes(org, vendor_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Logo not found")
    data, content_type = result
    return Response(content=data, media_type=content_type)


@router.delete("/{vendor_id}", status_code=204)
def delete_vendor(vendor_id: str, misty_session: str | None = Cookie(default=None)):
    user = _require_user(misty_session)
    if not authz_service.can(user, "vendor.manage"):
        raise HTTPException(status_code=403, detail="Forbidden")
    org = identity_service.get_org()
    deleted = vendors_service.delete_vendor(org, vendor_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Vendor not found")
