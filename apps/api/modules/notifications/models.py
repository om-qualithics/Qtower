import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.core.db import Base

NotificationStatus = PgEnum("sent", "failed", name="notification_status", create_type=False)


class NotificationLog(Base):
    """One row per send attempt (mock or live) - the audit-trail role
    llm_usage_log plays for ai_gateway. org_id is nullable since a future
    system-level notification (not tied to one org) could use the same
    log; every current caller sets it."""

    __tablename__ = "notification_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("org.id"), nullable=True)

    to_emails: Mapped[list] = mapped_column(JSONB, nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(NotificationStatus, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
