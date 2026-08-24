import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.core.db import Base


class DeploymentConfig(Base):
    """One row per org (handoff §2.4: branding is data, not hardcoded).
    Also holds the license payload in the same row per handoff's literal
    table sketch (§5) - not a separate table.
    """

    __tablename__ = "deployment_config"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("org.id"), nullable=False, unique=True)

    org_display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    primary_color: Mapped[str | None] = mapped_column(String(32), nullable=True)
    secondary_color: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email_templates: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    escalation_notify_override_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tool_assessment_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)

    license_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    license_seat_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    license_expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    enabled_feature_modules: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    license_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    license_validated_at: Mapped[datetime | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )
