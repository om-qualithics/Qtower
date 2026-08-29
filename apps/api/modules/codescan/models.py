import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.core.db import Base

ScanRunStatus = PgEnum("queued", "running", "complete", "failed", name="scan_run_status", create_type=False)
FindingSeverity = PgEnum("critical", "high", "medium", "low", name="finding_severity", create_type=False)
FindingConfidence = PgEnum("high", "medium", "low", name="finding_confidence", create_type=False)


class GithubConnection(Base):
    """At most one row per org (unique org_id, same "replace, not append"
    shape as OrgSsoConnection) - a self-owned GitHub App the org created
    and installed inside its own GitHub org (see plan: no shared vendor
    App, no callback URL, no centrally-hosted token-minting service).
    private_key_encrypted is the App's PEM private key, encrypted at rest
    via core/crypto.py - never returned by any GET endpoint."""

    __tablename__ = "github_connection"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("org.id"), nullable=False, unique=True)

    app_id: Mapped[str] = mapped_column(Text, nullable=False)
    app_slug: Mapped[str | None] = mapped_column(Text, nullable=True)
    installation_id: Mapped[str] = mapped_column(Text, nullable=False)
    private_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    account_login: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )


class ScanRun(Base):
    """One code scan against one repo. repo_full_name (e.g. "acme/backend")
    is stored directly, not FK'd to a persisted repo table - repos are
    discovered live from the GitHub installation each time (see plan:
    avoids a stale, separately-maintained repo list)."""

    __tablename__ = "scan_run"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("org.id"), nullable=False)
    github_connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("github_connection.id"), nullable=False
    )

    repo_full_name: Mapped[str] = mapped_column(Text, nullable=False)
    commit_sha: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(ScanRunStatus, nullable=False, server_default="queued")

    triggered_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    report_pdf_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))


class Finding(Base):
    """One deduplicated finding from a scan. category is a free-text key
    into codescan/taxonomy.py's static Tier-1 list (not a DB enum - a
    future phase adding categories shouldn't need a migration, same
    "taxonomy as code" precedent as policy's tier keys). sources is the
    list of tool names that corroborated this exact (file_path,
    line_start, category) - see tasks.py's dedup step."""

    __tablename__ = "finding"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("org.id"), nullable=False)
    scan_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scan_run.id"), nullable=False)

    category: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(FindingSeverity, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    line_start: Mapped[int | None] = mapped_column(nullable=True)
    line_end: Mapped[int | None] = mapped_column(nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    confidence: Mapped[str] = mapped_column(FindingConfidence, nullable=False, server_default="medium")

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
