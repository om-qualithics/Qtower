import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.core.db import Base

ToolRequestType = PgEnum("tool", "feature", "webextension", name="tool_request_type", create_type=False)
ToolRequestStatus = PgEnum("pending", "approved", "rejected", name="tool_request_status", create_type=False)
ToolAssessmentStatus = PgEnum(
    "pending", "complete", "failed", "skipped", name="tool_assessment_status", create_type=False
)
ToolAssessmentResult = PgEnum(
    "approvable", "needs_review", "cannot_approve", name="tool_assessment_result", create_type=False
)


class ApprovedTool(Base):
    """One row per org-approved tool/feature/webextension - the catalog
    every role browses. Only source_type="tool" rows get an "Access Now"
    button (an "enterprise account" only makes sense for a full tool);
    feature/webextension rows still live in the same catalog."""

    __tablename__ = "approved_tool"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("org.id"), nullable=False)

    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(ToolRequestType, nullable=False, server_default="tool")
    access_url: Mapped[str] = mapped_column(Text, nullable=False)
    allowed_tiers: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_from_request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tool_request.id"), nullable=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )


class ToolRequest(Base):
    """A request to add a tool/feature/webextension to the org's approved
    catalog. AI assessment (ai_assessment_*) is a precheck only - it never
    sets status itself, that's always a human decision via
    service.approve_request()/reject_request()."""

    __tablename__ = "tool_request"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("org.id"), nullable=False)

    request_type: Mapped[str] = mapped_column(ToolRequestType, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[str] = mapped_column(Text, nullable=False)
    intended_use_case: Mapped[str] = mapped_column(Text, nullable=False)
    data_tiers: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    requires_enterprise_account: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    status: Mapped[str] = mapped_column(ToolRequestStatus, nullable=False, server_default="pending")

    ai_assessment_status: Mapped[str] = mapped_column(ToolAssessmentStatus, nullable=False, server_default="pending")
    ai_assessment_result: Mapped[str | None] = mapped_column(ToolAssessmentResult, nullable=True)
    ai_assessment_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    requested_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    resulting_tool_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("approved_tool.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )
