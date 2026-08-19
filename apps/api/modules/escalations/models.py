import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.core.db import Base

# related_tool_request_id/related_policy_id below reference these tables
# by string FK ("tool_request.id"/"policy.id"), which only resolves once
# their model classes have been imported somewhere in the process (that's
# how SQLAlchemy's declarative registry gets populated) - importing them
# here keeps this module self-sufficient regardless of test run order,
# rather than relying on some other test file happening to import them
# first.
from apps.api.modules.policy.models import Policy  # noqa: F401
from apps.api.modules.tools.models import ToolRequest  # noqa: F401

EscalationCategory = PgEnum(
    "policy_violation",
    "unapproved_tool_use",
    "data_exposure_concern",
    "other",
    name="escalation_category",
    create_type=False,
)
EscalationStatus = PgEnum("open", "in_review", "resolved", name="escalation_status", create_type=False)


class Escalation(Base):
    """Free-text issue report (handoff §5e) - any authenticated user can
    raise one, govern/assure triage it. related_tool_request_id/
    related_policy_id are nullable optional links; the UI for choosing
    what to link is deferred (see plan) - the columns exist for a future
    picker to fill in."""

    __tablename__ = "escalation"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("org.id"), nullable=False)

    reporter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    category: Mapped[str] = mapped_column(EscalationCategory, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    related_tool_request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tool_request.id"), nullable=True
    )
    related_policy_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("policy.id"), nullable=True)

    status: Mapped[str] = mapped_column(EscalationStatus, nullable=False, server_default="open")
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    attachment_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachment_filename: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )
