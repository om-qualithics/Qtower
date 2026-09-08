import uuid
from datetime import date, datetime, timezone

from sqlalchemy import ForeignKey, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.core.db import Base

VendorType = PgEnum("commercial", "open_source", name="vendor_type", create_type=False)
VendorStatus = PgEnum("approved", "needs_review", "restricted", "pending", name="vendor_status", create_type=False)
VendorRequestStatus = PgEnum("pending", "approved", "rejected", name="vendor_request_status", create_type=False)
VendorChecklistTier = PgEnum("must_have", "good_to_have", "optional", name="vendor_checklist_tier", create_type=False)
VendorChecklistAppliesTo = PgEnum(
    "commercial", "open_source", "both", name="vendor_checklist_applies_to", create_type=False
)
VendorChecklistAnswer = PgEnum(
    "yes", "no", "partial", "not_applicable", name="vendor_checklist_answer", create_type=False
)


class Vendor(Base):
    """One row per org-approved (or pending/restricted) commercial or
    open-source AI vendor - the Vendor Register catalog. status/
    overall_score are computed by scoring.score_vendor() every time
    service.update_checklist_responses() runs, never set directly."""

    __tablename__ = "vendor"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("org.id"), nullable=False)

    name: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(VendorType, nullable=False)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    website_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(VendorStatus, nullable=False, server_default="pending")
    overall_score: Mapped[float | None] = mapped_column(Numeric, nullable=True)

    created_from_request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vendor_request.id"), nullable=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )


class VendorRequest(Base):
    """A request to add a commercial or open-source vendor to the org's
    Vendor Register. No AI precheck (unlike tool_request/project_request) -
    vendor evaluation is deterministic checklist scoring, see scoring.py.
    The requester answers the checklist directly on the request (see
    VendorRequestChecklistResponse below) - projected_status/overall_score
    are computed synchronously at submission via the same
    scoring.score_vendor() an approved Vendor uses, so the requester (and
    an approver reviewing the queue) sees the likely outcome immediately,
    not after a separate post-approval checklist step."""

    __tablename__ = "vendor_request"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("org.id"), nullable=False)

    requested_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(VendorType, nullable=False)
    website_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    business_justification: Mapped[str] = mapped_column(Text, nullable=False)

    projected_status: Mapped[str | None] = mapped_column(VendorStatus, nullable=True)
    overall_score: Mapped[float | None] = mapped_column(Numeric, nullable=True)

    resulting_vendor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vendor.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(VendorRequestStatus, nullable=False, server_default="pending")
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )


class VendorRequestChecklistResponse(Base):
    """The requester's checklist answers, captured at submission time -
    org-scoped (own org_id, RLS), mirrors VendorChecklistResponse's shape
    exactly. Copied into real VendorChecklistResponse rows for the new
    Vendor on approve_vendor_request() - the request's own rows are left
    in place afterward as a record of what was originally submitted."""

    __tablename__ = "vendor_request_checklist_response"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("org.id"), nullable=False)
    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vendor_request.id"), nullable=False)
    checklist_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vendor_checklist_item.id"), nullable=False
    )
    answer: Mapped[str] = mapped_column(VendorChecklistAnswer, nullable=False)
    evidence_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))


class VendorChecklistItem(Base):
    """Shared reference catalog (no org_id, no RLS - same precedent as
    training.models.TrainingModule) - one fixed question set every org
    scores vendors against. Seeded from Vendor Checklist.xlsx via
    scripts/seed_vendor_checklist.py; `key` is a stable slug so re-running
    the seed script is a safe idempotent upsert, not a duplicate insert."""

    __tablename__ = "vendor_checklist_item"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    tier: Mapped[str] = mapped_column(VendorChecklistTier, nullable=False)
    applies_to: Mapped[str] = mapped_column(VendorChecklistAppliesTo, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)


class VendorChecklistResponse(Base):
    """One org's answer to one checklist question for one vendor - the
    actual tenant data (own org_id + RLS, not inferred via the vendor_id
    join, matching every other org-scoped table in this schema)."""

    __tablename__ = "vendor_checklist_response"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("org.id"), nullable=False)
    vendor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vendor.id"), nullable=False)
    checklist_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vendor_checklist_item.id"), nullable=False
    )
    answer: Mapped[str] = mapped_column(VendorChecklistAnswer, nullable=False)
    evidence_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_verified_date: Mapped[date | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )
