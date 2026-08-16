"""llm_usage_log (ai_gateway call accounting)

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "llm_usage_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("org.id"), nullable=False),
        sa.Column("feature", sa.String(128), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("prompt_tokens", sa.Integer, nullable=False),
        sa.Column("completion_tokens", sa.Integer, nullable=False),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.execute('ALTER TABLE "llm_usage_log" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "llm_usage_log" FORCE ROW LEVEL SECURITY')
    op.execute(
        """
        CREATE POLICY llm_usage_log_org_isolation ON "llm_usage_log"
        USING (org_id = current_setting('app.current_org_id', true)::uuid)
        WITH CHECK (org_id = current_setting('app.current_org_id', true)::uuid)
        """
    )


def downgrade() -> None:
    op.execute('DROP POLICY IF EXISTS llm_usage_log_org_isolation ON "llm_usage_log"')
    op.drop_table("llm_usage_log")
