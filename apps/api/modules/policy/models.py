import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.core.db import Base

PolicyStatus = PgEnum("draft", "generated", name="policy_status", create_type=False)


class Policy(Base):
    """One row per policy draft/generation (handoff §5's "policy content is
    structured Postgres data, not files" - answers live here; only the
    rendered docx is an opaque MinIO object). draft -> generated is the
    full lifecycle this milestone builds; publish/version-bump is future
    scope (see aboutproject.md Milestone 5).
    """

    __tablename__ = "policy"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("org.id"), nullable=False)

    status: Mapped[str] = mapped_column(PolicyStatus, nullable=False, server_default="draft")
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")

    policy_owner_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approver_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    answers: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")

    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(nullable=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )
