"""codescan: github_connection, scan_run, finding - all org-scoped, RLS
on every table. See aboutproject.md / the build plan's Milestone 13 for
the two architecture decisions (self-owned GitHub App per org, no
per-scan container) this schema follows from.

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _rls(table: str, policy: str) -> None:
    # semgrep flags all three op.execute() calls below as a possible SQL
    # injection (formatted-sql-query / sqlalchemy-execute-raw-query,
    # confirmed via a real Code Scan of this repo, semgrep's own confidence
    # was already "low"). False positive: `table`/`policy` are always
    # hardcoded string literals at the three call sites below (never a
    # variable that traces back to user input), and this runs once at
    # `alembic upgrade` time from the CLI, never in a request path - the
    # same "RLS setup via f-string DDL with literal names" shape every
    # migration in this repo uses (see CLAUDE.md's RLS pattern). Marked
    # inline rather than a directory-wide semgrep ignore so a genuinely
    # different finding in a future migration still surfaces.
    op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')  # nosemgrep
    op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')  # nosemgrep
    op.execute(  # nosemgrep
        f"""
        CREATE POLICY {policy} ON "{table}"
        USING (org_id = current_setting('app.current_org_id', true)::uuid)
        WITH CHECK (org_id = current_setting('app.current_org_id', true)::uuid)
        """
    )


def upgrade() -> None:
    scan_status = postgresql.ENUM("queued", "running", "complete", "failed", name="scan_run_status")
    scan_status.create(op.get_bind(), checkfirst=True)
    scan_status_nc = postgresql.ENUM(
        "queued", "running", "complete", "failed", name="scan_run_status", create_type=False
    )

    severity = postgresql.ENUM("critical", "high", "medium", "low", name="finding_severity")
    severity.create(op.get_bind(), checkfirst=True)
    severity_nc = postgresql.ENUM("critical", "high", "medium", "low", name="finding_severity", create_type=False)

    confidence = postgresql.ENUM("high", "medium", "low", name="finding_confidence")
    confidence.create(op.get_bind(), checkfirst=True)
    confidence_nc = postgresql.ENUM("high", "medium", "low", name="finding_confidence", create_type=False)

    op.create_table(
        "github_connection",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("org.id"), nullable=False, unique=True),
        sa.Column("app_id", sa.Text, nullable=False),
        sa.Column("app_slug", sa.Text, nullable=True),
        sa.Column("installation_id", sa.Text, nullable=False),
        sa.Column("private_key_encrypted", sa.Text, nullable=False),
        sa.Column("account_login", sa.Text, nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_github_connection_org_id", "github_connection", ["org_id"])
    _rls("github_connection", "github_connection_org_isolation")

    op.create_table(
        "scan_run",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("org.id"), nullable=False),
        sa.Column(
            "github_connection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("github_connection.id"), nullable=False
        ),
        sa.Column("repo_full_name", sa.Text, nullable=False),
        sa.Column("commit_sha", sa.Text, nullable=True),
        sa.Column("status", scan_status_nc, nullable=False, server_default="queued"),
        sa.Column("triggered_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("report_pdf_key", sa.Text, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_scan_run_org_id", "scan_run", ["org_id"])
    _rls("scan_run", "scan_run_org_isolation")

    op.create_table(
        "finding",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("org.id"), nullable=False),
        sa.Column("scan_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scan_run.id"), nullable=False),
        sa.Column("category", sa.Text, nullable=False),
        sa.Column("severity", severity_nc, nullable=False),
        sa.Column("file_path", sa.Text, nullable=False),
        sa.Column("line_start", sa.Integer, nullable=True),
        sa.Column("line_end", sa.Integer, nullable=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("sources", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("confidence", confidence_nc, nullable=False, server_default="medium"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_finding_org_id", "finding", ["org_id"])
    op.create_index("ix_finding_scan_run_id", "finding", ["scan_run_id"])
    _rls("finding", "finding_org_isolation")

    # Critical findings auto-create an Escalation (tasks.py) tagged with
    # this new category - pure addition to escalation_category, same
    # ALTER TYPE ... ADD VALUE pattern migration 0011 already used for
    # tool_assessment_status.
    op.execute("ALTER TYPE escalation_category ADD VALUE IF NOT EXISTS 'code_scan_critical'")


def downgrade() -> None:
    op.execute('DROP POLICY IF EXISTS finding_org_isolation ON "finding"')
    op.drop_index("ix_finding_scan_run_id", table_name="finding")
    op.drop_index("ix_finding_org_id", table_name="finding")
    op.drop_table("finding")
    postgresql.ENUM(name="finding_confidence").drop(op.get_bind())
    postgresql.ENUM(name="finding_severity").drop(op.get_bind())

    op.execute('DROP POLICY IF EXISTS scan_run_org_isolation ON "scan_run"')
    op.drop_index("ix_scan_run_org_id", table_name="scan_run")
    op.drop_table("scan_run")
    postgresql.ENUM(name="scan_run_status").drop(op.get_bind())

    op.execute('DROP POLICY IF EXISTS github_connection_org_isolation ON "github_connection"')
    op.drop_index("ix_github_connection_org_id", table_name="github_connection")
    op.drop_table("github_connection")
