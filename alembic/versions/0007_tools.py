"""tools: approved_tool catalog + tool_request approval workflow

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    tool_request_type = postgresql.ENUM("tool", "feature", "webextension", name="tool_request_type")
    tool_request_type.create(op.get_bind(), checkfirst=True)
    tool_request_status = postgresql.ENUM("pending", "approved", "rejected", name="tool_request_status")
    tool_request_status.create(op.get_bind(), checkfirst=True)
    tool_assessment_status = postgresql.ENUM("pending", "complete", "failed", name="tool_assessment_status")
    tool_assessment_status.create(op.get_bind(), checkfirst=True)
    tool_assessment_result = postgresql.ENUM(
        "approvable", "needs_review", "cannot_approve", name="tool_assessment_result"
    )
    tool_assessment_result.create(op.get_bind(), checkfirst=True)

    tool_request_type_nc = postgresql.ENUM(
        "tool", "feature", "webextension", name="tool_request_type", create_type=False
    )
    tool_request_status_nc = postgresql.ENUM(
        "pending", "approved", "rejected", name="tool_request_status", create_type=False
    )
    tool_assessment_status_nc = postgresql.ENUM(
        "pending", "complete", "failed", name="tool_assessment_status", create_type=False
    )
    tool_assessment_result_nc = postgresql.ENUM(
        "approvable", "needs_review", "cannot_approve", name="tool_assessment_result", create_type=False
    )

    # tool_request is created first with resulting_tool_id as a plain
    # column (no FK yet) - approved_tool doesn't exist yet and the two
    # tables reference each other, so the second FK is added after both
    # tables exist.
    op.create_table(
        "tool_request",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("org.id"), nullable=False),
        sa.Column("request_type", tool_request_type_nc, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("link", sa.Text, nullable=False),
        sa.Column("intended_use_case", sa.Text, nullable=False),
        sa.Column("status", tool_request_status_nc, nullable=False, server_default="pending"),
        sa.Column("ai_assessment_status", tool_assessment_status_nc, nullable=False, server_default="pending"),
        sa.Column("ai_assessment_result", tool_assessment_result_nc, nullable=True),
        sa.Column("ai_assessment_explanation", sa.Text, nullable=True),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("decided_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text, nullable=True),
        sa.Column("resulting_tool_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_tool_request_org_id", "tool_request", ["org_id"])
    op.execute('ALTER TABLE "tool_request" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "tool_request" FORCE ROW LEVEL SECURITY')
    op.execute(
        """
        CREATE POLICY tool_request_org_isolation ON "tool_request"
        USING (org_id = current_setting('app.current_org_id', true)::uuid)
        WITH CHECK (org_id = current_setting('app.current_org_id', true)::uuid)
        """
    )

    op.create_table(
        "approved_tool",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("org.id"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("source_type", tool_request_type_nc, nullable=False, server_default="tool"),
        sa.Column("access_url", sa.Text, nullable=False),
        sa.Column("allowed_tiers", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("details", sa.Text, nullable=True),
        sa.Column("created_from_request_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tool_request.id"), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_approved_tool_org_id", "approved_tool", ["org_id"])
    op.execute('ALTER TABLE "approved_tool" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "approved_tool" FORCE ROW LEVEL SECURITY')
    op.execute(
        """
        CREATE POLICY approved_tool_org_isolation ON "approved_tool"
        USING (org_id = current_setting('app.current_org_id', true)::uuid)
        WITH CHECK (org_id = current_setting('app.current_org_id', true)::uuid)
        """
    )

    op.create_foreign_key(
        "fk_tool_request_resulting_tool",
        "tool_request",
        "approved_tool",
        ["resulting_tool_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_tool_request_resulting_tool", "tool_request", type_="foreignkey")

    op.execute('DROP POLICY IF EXISTS approved_tool_org_isolation ON "approved_tool"')
    op.drop_index("ix_approved_tool_org_id", table_name="approved_tool")
    op.drop_table("approved_tool")

    op.execute('DROP POLICY IF EXISTS tool_request_org_isolation ON "tool_request"')
    op.drop_index("ix_tool_request_org_id", table_name="tool_request")
    op.drop_table("tool_request")

    postgresql.ENUM(name="tool_assessment_result").drop(op.get_bind())
    postgresql.ENUM(name="tool_assessment_status").drop(op.get_bind())
    postgresql.ENUM(name="tool_request_status").drop(op.get_bind())
    postgresql.ENUM(name="tool_request_type").drop(op.get_bind())
