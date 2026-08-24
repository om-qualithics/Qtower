import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.core.db import Base

TrainingVideoType = PgEnum("placeholder", "file", "embed", name="training_video_type", create_type=False)
TrainingCompletionStatus = PgEnum(
    "not_started", "in_progress", "completed", name="training_completion_status", create_type=False
)


class TrainingModule(Base):
    """The training curriculum itself - deliberately NOT org-scoped and has
    no RLS policy. This is a scope call, not an oversight: the content is
    generic AI-usage training identical for every org, the same precedent
    already set for the policy template (one copy in MinIO, Milestone 5)
    and the policy question catalog (static code, Milestone 5) - neither
    duplicated per tenant. Per-user completion (TrainingCompletion below)
    *is* org-scoped, since that's the actual tenant data.

    video_url stays null (video_type="placeholder") until a real video is
    produced - flipping video_type/video_url via training.manage is the
    entire "plug in the video" story this milestone exists to set up.
    """

    __tablename__ = "training_module"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    order_index: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)

    video_type: Mapped[str] = mapped_column(TrainingVideoType, nullable=False, server_default="placeholder")
    video_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # [{"id": str, "prompt": str, "options": [str, ...] | None}, ...] -
    # ungraded checkpoints (see plan), options=None means a free-text
    # question instead of multiple choice.
    questions: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )


class TrainingCompletion(Base):
    """Per-user, per-module progress - the actual tenant data (org_id +
    RLS, standard pattern). One row per (org, user, module), upserted as
    the user progresses - not an event log, mirrors policy's
    single-draft-per-concept shape."""

    __tablename__ = "training_completion"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("org.id"), nullable=False)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    module_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("training_module.id"), nullable=False)

    status: Mapped[str] = mapped_column(TrainingCompletionStatus, nullable=False, server_default="not_started")
    answers: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )
