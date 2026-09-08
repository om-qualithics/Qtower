import uuid
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.core import storage
from apps.api.core.db import SessionLocal, org_scoped_session
from apps.api.core.media import logo_storage_key
from apps.api.modules.identity.models import Org, User
from apps.api.modules.vendors.models import (
    Vendor,
    VendorChecklistItem,
    VendorChecklistResponse,
    VendorRequest,
    VendorRequestChecklistResponse,
)
from apps.api.modules.vendors.scoring import ChecklistAnswer, score_vendor

VENDOR_TYPES = ("commercial", "open_source")
CHECKLIST_ANSWERS = ("yes", "no", "partial", "not_applicable")


class VendorValidationError(Exception):
    pass


class VendorRequestDuplicateError(Exception):
    def __init__(self, existing_vendor: Vendor) -> None:
        self.existing_vendor = existing_vendor
        super().__init__(f"'{existing_vendor.name}' is already in the Vendor Register")


class VendorApprovalError(Exception):
    pass


def _normalize_name(name: str) -> str:
    return name.strip().lower()


@contextmanager
def _catalog_session() -> Generator[Session, None, None]:
    """vendor_checklist_item has no org_id and no RLS policy (shared
    reference catalog, see models.py) - read/written through a plain
    session, never org_scoped_session. Same pattern as
    training/service.py::_catalog_session()."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def list_checklist_items(applies_to: str | None = None) -> list[VendorChecklistItem]:
    with _catalog_session() as db:
        query = select(VendorChecklistItem)
        if applies_to is not None:
            query = query.where(VendorChecklistItem.applies_to.in_([applies_to, "both"]))
        items = db.scalars(query.order_by(VendorChecklistItem.sort_order)).all()
        for item in items:
            db.expunge(item)
        return list(items)


def _score_from_answers(responses: list[dict], tier_by_item_id: dict[str, str]) -> tuple[str, float]:
    answers = [
        ChecklistAnswer(
            checklist_item_id=r["checklist_item_id"],
            tier=tier_by_item_id.get(r["checklist_item_id"], "optional"),
            answer=r["answer"],
        )
        for r in responses
    ]
    return score_vendor(answers)


def list_vendors(org: Org, *, type_: str | None = None) -> list[Vendor]:
    with org_scoped_session(str(org.id)) as db:
        query = select(Vendor).where(Vendor.org_id == org.id)
        if type_ is not None:
            query = query.where(Vendor.type == type_)
        vendors = db.scalars(query.order_by(Vendor.name)).all()
        for vendor in vendors:
            db.expunge(vendor)
        return list(vendors)


def get_vendor(org: Org, vendor_id: str) -> Vendor | None:
    with org_scoped_session(str(org.id)) as db:
        vendor = db.get(Vendor, uuid.UUID(vendor_id))
        if vendor is None or str(vendor.org_id) != str(org.id):
            return None
        db.expunge(vendor)
        return vendor


def get_vendor_responses(org: Org, vendor_id: str) -> list[VendorChecklistResponse]:
    with org_scoped_session(str(org.id)) as db:
        responses = db.scalars(
            select(VendorChecklistResponse).where(
                VendorChecklistResponse.org_id == org.id, VendorChecklistResponse.vendor_id == uuid.UUID(vendor_id)
            )
        ).all()
        for response in responses:
            db.expunge(response)
        return list(responses)


def update_vendor_logo_url(org: Org, vendor_id: str, logo_url: str | None) -> Vendor | None:
    """The paste-a-URL-directly path (Milestone 17) - see
    upload_vendor_logo() for the alternative upload-to-MinIO path."""
    with org_scoped_session(str(org.id)) as db:
        vendor = db.get(Vendor, uuid.UUID(vendor_id))
        if vendor is None or str(vendor.org_id) != str(org.id):
            return None
        vendor.logo_url = logo_url.strip() if logo_url and logo_url.strip() else None
        db.flush()
        db.refresh(vendor)
        db.expunge(vendor)
        return vendor


def upload_vendor_logo(org: Org, vendor_id: str, content_type: str, data: bytes) -> Vendor | None:
    """Mirrors tools/service.py::upload_tool_logo() exactly - stores at a
    fixed per-vendor key (overwrites any previous logo) and points
    logo_url at this app's own streaming route, not a MinIO/S3 URL
    directly (see that function's docstring for why)."""
    with org_scoped_session(str(org.id)) as db:
        vendor = db.get(Vendor, uuid.UUID(vendor_id))
        if vendor is None or str(vendor.org_id) != str(org.id):
            return None
        key = logo_storage_key("vendor", str(org.id), vendor_id)
        storage.upload_bytes(key, data, content_type)
        vendor.logo_url = f"/vendors/{vendor_id}/logo-file"
        db.flush()
        db.refresh(vendor)
        db.expunge(vendor)
        return vendor


def get_vendor_logo_bytes(org: Org, vendor_id: str) -> tuple[bytes, str] | None:
    with org_scoped_session(str(org.id)) as db:
        vendor = db.get(Vendor, uuid.UUID(vendor_id))
        if vendor is None or str(vendor.org_id) != str(org.id):
            return None
    key = logo_storage_key("vendor", str(org.id), vendor_id)
    return storage.download_bytes_with_content_type(key)


def delete_vendor(org: Org, vendor_id: str) -> bool:
    with org_scoped_session(str(org.id)) as db:
        vendor = db.get(Vendor, uuid.UUID(vendor_id))
        if vendor is None or str(vendor.org_id) != str(org.id):
            return False
        # Both sides of the circular FK (see the migration's note) must be
        # cleared before the row can be deleted - identical pattern to
        # tools/service.py::delete_approved_tool().
        vendor.created_from_request_id = None
        db.flush()
        referencing_requests = db.scalars(
            select(VendorRequest).where(VendorRequest.resulting_vendor_id == vendor.id)
        ).all()
        for request in referencing_requests:
            request.resulting_vendor_id = None
        db.flush()
        responses = db.scalars(
            select(VendorChecklistResponse).where(VendorChecklistResponse.vendor_id == vendor.id)
        ).all()
        for response in responses:
            db.delete(response)
        db.flush()
        db.delete(vendor)
        return True


def create_vendor_request(
    org: Org,
    user: User,
    name: str,
    type_: str,
    website_url: str | None,
    justification: str,
    responses: list[dict] | None = None,
) -> VendorRequest:
    if type_ not in VENDOR_TYPES:
        raise VendorValidationError(f"Unknown vendor type: {type_!r}")
    if not name.strip():
        raise VendorValidationError("Name is required")
    if not justification.strip():
        raise VendorValidationError("Business justification is required")

    responses = responses or []
    for r in responses:
        if r["answer"] not in CHECKLIST_ANSWERS:
            raise VendorValidationError(f"Unknown answer: {r['answer']!r}")

    with _catalog_session() as catalog_db:
        items = catalog_db.scalars(select(VendorChecklistItem)).all()
        tier_by_item_id = {str(item.id): item.tier for item in items}
        applies_to_by_item_id = {str(item.id): item.applies_to for item in items}

    for r in responses:
        item_id = r["checklist_item_id"]
        if item_id not in tier_by_item_id:
            raise VendorValidationError(f"Unknown checklist item: {item_id!r}")
        applies_to = applies_to_by_item_id[item_id]
        if applies_to not in (type_, "both"):
            raise VendorValidationError(f"Checklist item {item_id!r} does not apply to vendor type {type_!r}")

    # Computed here, not deferred to approval - the requester (and anyone
    # reviewing the pending queue) sees the likely outcome immediately,
    # same score_vendor() an approved Vendor uses (see the module
    # docstring on VendorRequest).
    projected_status, overall_score = _score_from_answers(responses, tier_by_item_id)

    normalized = _normalize_name(name)
    with org_scoped_session(str(org.id)) as db:
        existing_vendors = db.scalars(select(Vendor).where(Vendor.org_id == org.id)).all()
        for vendor in existing_vendors:
            if _normalize_name(vendor.name) == normalized:
                db.expunge(vendor)
                raise VendorRequestDuplicateError(vendor)

        request = VendorRequest(
            org_id=org.id,
            requested_by=user.id,
            name=name.strip(),
            type=type_,
            website_url=website_url.strip() if website_url else None,
            business_justification=justification.strip(),
            projected_status=projected_status,
            overall_score=overall_score,
        )
        db.add(request)
        db.flush()

        for r in responses:
            db.add(
                VendorRequestChecklistResponse(
                    org_id=org.id,
                    request_id=request.id,
                    checklist_item_id=uuid.UUID(r["checklist_item_id"]),
                    answer=r["answer"],
                    evidence_note=r.get("evidence_note"),
                )
            )
        db.flush()
        db.refresh(request)
        db.expunge(request)
        return request


def get_vendor_request_responses(org: Org, request_id: str) -> list[VendorRequestChecklistResponse]:
    with org_scoped_session(str(org.id)) as db:
        responses = db.scalars(
            select(VendorRequestChecklistResponse).where(
                VendorRequestChecklistResponse.org_id == org.id,
                VendorRequestChecklistResponse.request_id == uuid.UUID(request_id),
            )
        ).all()
        for response in responses:
            db.expunge(response)
        return list(responses)


def list_vendor_requests(org: Org, *, mine: User | None = None, pending_only: bool = False) -> list[VendorRequest]:
    with org_scoped_session(str(org.id)) as db:
        query = select(VendorRequest).where(VendorRequest.org_id == org.id)
        if mine is not None:
            query = query.where(VendorRequest.requested_by == mine.id)
        if pending_only:
            query = query.where(VendorRequest.status == "pending")
        requests = db.scalars(query.order_by(VendorRequest.created_at.desc())).all()
        for request in requests:
            db.expunge(request)
        return list(requests)


def get_vendor_request(org: Org, request_id: str) -> VendorRequest | None:
    with org_scoped_session(str(org.id)) as db:
        request = db.get(VendorRequest, uuid.UUID(request_id))
        if request is None or str(request.org_id) != str(org.id):
            return None
        db.expunge(request)
        return request


def approve_vendor_request(org: Org, request_id: str, approver: User) -> VendorRequest:
    request = get_vendor_request(org, request_id)
    if request is None:
        raise VendorApprovalError("Request not found")
    if request.status != "pending":
        raise VendorApprovalError(f"Only a pending request can be approved (current status: {request.status})")
    if request.requested_by == approver.id:
        raise VendorApprovalError("You cannot approve your own request")

    with _catalog_session() as catalog_db:
        items = catalog_db.scalars(select(VendorChecklistItem)).all()
        tier_by_item_id = {str(item.id): item.tier for item in items}

    with org_scoped_session(str(org.id)) as db:
        target = db.get(VendorRequest, uuid.UUID(request_id))
        assert target is not None

        vendor = Vendor(
            org_id=org.id,
            name=target.name,
            type=target.type,
            website_url=target.website_url,
            created_from_request_id=target.id,
            created_by=approver.id,
        )
        db.add(vendor)
        db.flush()

        # Carry the requester's checklist answers over to the new Vendor
        # row rather than starting it blank - the request's own rows are
        # left in place as a record of what was originally submitted.
        request_responses = db.scalars(
            select(VendorRequestChecklistResponse).where(VendorRequestChecklistResponse.request_id == target.id)
        ).all()
        copied = [
            {"checklist_item_id": str(r.checklist_item_id), "answer": r.answer, "evidence_note": r.evidence_note}
            for r in request_responses
        ]
        for r in copied:
            db.add(
                VendorChecklistResponse(
                    org_id=org.id,
                    vendor_id=vendor.id,
                    checklist_item_id=uuid.UUID(r["checklist_item_id"]),
                    answer=r["answer"],
                    evidence_note=r["evidence_note"],
                )
            )
        # Recomputed fresh rather than copied from target.projected_status/
        # overall_score - same inputs, but this stays correct even if the
        # checklist catalog changed between request and approval.
        status, score = _score_from_answers(copied, tier_by_item_id)
        vendor.status = status
        vendor.overall_score = score

        target.status = "approved"
        target.decided_by = approver.id
        target.decided_at = datetime.now(timezone.utc)
        target.resulting_vendor_id = vendor.id

        db.flush()
        db.refresh(target)
        db.expunge(target)
        return target


def reject_vendor_request(org: Org, request_id: str, approver: User) -> VendorRequest:
    request = get_vendor_request(org, request_id)
    if request is None:
        raise VendorApprovalError("Request not found")
    if request.status != "pending":
        raise VendorApprovalError(f"Only a pending request can be rejected (current status: {request.status})")
    if request.requested_by == approver.id:
        raise VendorApprovalError("You cannot reject your own request")

    with org_scoped_session(str(org.id)) as db:
        target = db.get(VendorRequest, uuid.UUID(request_id))
        assert target is not None
        target.status = "rejected"
        target.decided_by = approver.id
        target.decided_at = datetime.now(timezone.utc)
        db.flush()
        db.refresh(target)
        db.expunge(target)
        return target


def update_checklist_responses(
    org: Org,
    vendor_id: str,
    responses: list[dict],
) -> Vendor | None:
    """Bulk upserts checklist responses and rescores the vendor
    synchronously in the same call - no Celery, no ai_gateway, per the
    deterministic-scoring design (scoring.py's module docstring)."""
    for r in responses:
        if r["answer"] not in CHECKLIST_ANSWERS:
            raise VendorValidationError(f"Unknown answer: {r['answer']!r}")

    with _catalog_session() as catalog_db:
        items = catalog_db.scalars(select(VendorChecklistItem)).all()
        tier_by_item_id = {str(item.id): item.tier for item in items}

    with org_scoped_session(str(org.id)) as db:
        vendor = db.get(Vendor, uuid.UUID(vendor_id))
        if vendor is None or str(vendor.org_id) != str(org.id):
            return None

        for r in responses:
            item_id = r["checklist_item_id"]
            if item_id not in tier_by_item_id:
                raise VendorValidationError(f"Unknown checklist item: {item_id!r}")
            existing = db.scalars(
                select(VendorChecklistResponse).where(
                    VendorChecklistResponse.vendor_id == vendor.id,
                    VendorChecklistResponse.checklist_item_id == uuid.UUID(item_id),
                )
            ).first()
            last_verified = r.get("last_verified_date")
            if existing is not None:
                existing.answer = r["answer"]
                existing.evidence_note = r.get("evidence_note")
                existing.last_verified_date = last_verified
            else:
                db.add(
                    VendorChecklistResponse(
                        org_id=org.id,
                        vendor_id=vendor.id,
                        checklist_item_id=uuid.UUID(item_id),
                        answer=r["answer"],
                        evidence_note=r.get("evidence_note"),
                        last_verified_date=last_verified,
                    )
                )
        db.flush()

        all_responses = db.scalars(
            select(VendorChecklistResponse).where(VendorChecklistResponse.vendor_id == vendor.id)
        ).all()
        answers = [
            ChecklistAnswer(
                checklist_item_id=str(resp.checklist_item_id),
                tier=tier_by_item_id.get(str(resp.checklist_item_id), "optional"),
                answer=resp.answer,
            )
            for resp in all_responses
        ]
        status, score = score_vendor(answers)
        vendor.status = status
        vendor.overall_score = score

        db.flush()
        db.refresh(vendor)
        db.expunge(vendor)
        return vendor
