import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.core.db import Base

# Reused as-is from tools/models.py - identical value sets, no reason to
# define a second enum type. project_assessment_status already carries
# "skipped" (added to tool_assessment_status in migration 0011), which
# has_active_policy()-gated project requests need from day one.
ProjectRequestStatus = PgEnum("pending", "approved", "rejected", name="tool_request_status", create_type=False)
ProjectAssessmentStatus = PgEnum(
    "pending", "complete", "failed", "skipped", name="tool_assessment_status", create_type=False
)
ProjectAssessmentResult = PgEnum(
    "approvable", "needs_review", "cannot_approve", name="tool_assessment_result", create_type=False
)
ProjectLifecycleStage = PgEnum("idea", "pilot", "production", "retired", name="project_lifecycle_stage", create_type=False)


class Project(Base):
    """One row per approved AI use-case/workflow - the third AI Center
    catalog, alongside approved_tool and vendor. Its linked tools/vendors
    live in ProjectToolLink/ProjectVendorLink (project_id side), copied
    over from the originating request's own link rows at approval time -
    see service.py::approve_project_request()."""

    __tablename__ = "project"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("org.id"), nullable=False)

    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    lifecycle_stage: Mapped[str] = mapped_column(ProjectLifecycleStage, nullable=False, server_default="idea")
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=True)

    created_from_request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_request.id"), nullable=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )


class ProjectRequest(Base):
    """A request to add an AI use-case/workflow to the org's Project
    inventory. Linking Tools/Vendors is not a hard gate (handoff §3.1/
    this app's build plan) - a project can submit with zero links, and an
    unregistered tool/vendor is tagged "not registered in inventory" via
    ProjectToolLink/ProjectVendorLink's other_name (structural, set at
    submission) rather than blocked. AI assessment mirrors
    tool_request's precheck exactly: skipped with no active policy,
    otherwise a Celery task calls ai_gateway and never auto-approves."""

    __tablename__ = "project_request"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("org.id"), nullable=False)

    requested_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    business_justification: Mapped[str] = mapped_column(Text, nullable=False)
    data_flow_description: Mapped[str] = mapped_column(Text, nullable=False)
    data_tiers: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    human_in_loop: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    status: Mapped[str] = mapped_column(ProjectRequestStatus, nullable=False, server_default="pending")

    project_assessment_status: Mapped[str] = mapped_column(
        ProjectAssessmentStatus, nullable=False, server_default="pending"
    )
    project_assessment_result: Mapped[str | None] = mapped_column(ProjectAssessmentResult, nullable=True)
    project_assessment_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    resulting_project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project.id"), nullable=True
    )
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )


class ProjectToolLink(Base):
    """One linked tool for a project or a still-pending request - exactly
    one of project_id/request_id is set (which "owner" this row belongs
    to: a request's proposed links before approval, or a real project's
    links after) and exactly one of tool_id/other_name is set (a real
    approved_tool vs. a free-text name for something not in the
    catalog). Both invariants are enforced in service.py, not a DB CHECK
    constraint, matching this schema's existing preference. On approval,
    a request's link rows are copied (not moved) into new project_id rows
    - see service.py::approve_project_request()."""

    __tablename__ = "project_tool_link"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("org.id"), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("project.id"), nullable=True)
    request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_request.id"), nullable=True
    )
    tool_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("approved_tool.id"), nullable=True)
    other_name: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))


class ProjectVendorLink(Base):
    """Same shape as ProjectToolLink, for linked vendors instead of
    tools - see that class's docstring for the two invariants."""

    __tablename__ = "project_vendor_link"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("org.id"), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("project.id"), nullable=True)
    request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_request.id"), nullable=True
    )
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("vendor.id"), nullable=True)
    other_name: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
