import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.core.db import Base

PolicyStatus = PgEnum("draft", "active", "archived", name="policy_status", create_type=False)
PolicySource = PgEnum("builder", "upload", name="policy_source", create_type=False)


class Policy(Base):
    """One row per policy draft/version (handoff §5's "policy content is
    structured Postgres data, not files" - answers live here; only the
    rendered docx is an opaque MinIO object).

    Lifecycle: draft -> active -> archived. Exactly one row per org may be
    "active" at a time (enforced by a partial unique index in the 0006
    migration, not just application logic) - approving a draft archives
    whatever was previously active. A draft with a non-null storage_key
    has a document attached (built via the wizard or uploaded directly)
    but isn't live until approved.
    """

    __tablename__ = "policy"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("org.id"), nullable=False)

    status: Mapped[str] = mapped_column(PolicyStatus, nullable=False, server_default="draft")
    source: Mapped[str] = mapped_column(PolicySource, nullable=False, server_default="builder")
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")

    policy_owner_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approver_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    answers: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")

    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(nullable=True)

    approved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )
