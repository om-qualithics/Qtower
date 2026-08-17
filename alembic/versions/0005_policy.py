"""policy (AI policy builder drafts + generated docs)

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    policy_status = postgresql.ENUM("draft", "generated", name="policy_status", create_type=False)
    policy_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "policy",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("org.id"), nullable=False),
        sa.Column("status", policy_status, nullable=False, server_default="draft"),
        sa.Column("current_step", sa.Integer, nullable=False, server_default="1"),
        sa.Column("policy_owner_name", sa.String(255), nullable=True),
        sa.Column("approver_name", sa.String(255), nullable=True),
        sa.Column("answers", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("storage_key", sa.Text, nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_policy_org_id", "policy", ["org_id"])
    op.execute('ALTER TABLE "policy" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "policy" FORCE ROW LEVEL SECURITY')
    op.execute(
        """
        CREATE POLICY policy_org_isolation ON "policy"
        USING (org_id = current_setting('app.current_org_id', true)::uuid)
        WITH CHECK (org_id = current_setting('app.current_org_id', true)::uuid)
        """
    )


def downgrade() -> None:
    op.execute('DROP POLICY IF EXISTS policy_org_isolation ON "policy"')
    op.drop_index("ix_policy_org_id", table_name="policy")
    op.drop_table("policy")
    postgresql.ENUM(name="policy_status").drop(op.get_bind())
