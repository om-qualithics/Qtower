"""org and user tables, RLS proven on user

Revision ID: 0001
Revises:
Create Date: 2026-08-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "org",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "user",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("org.id"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_org_id", "user", ["org_id"])

    # Multi-tenant isolation proof (handoff §2.1): every org-scoped table
    # gets RLS keyed on app.current_org_id, enforced even for the table
    # owner (FORCE), not just filtered at the application layer.
    op.execute('ALTER TABLE "user" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "user" FORCE ROW LEVEL SECURITY')
    op.execute(
        """
        CREATE POLICY user_org_isolation ON "user"
        USING (org_id = current_setting('app.current_org_id', true)::uuid)
        WITH CHECK (org_id = current_setting('app.current_org_id', true)::uuid)
        """
    )


def downgrade() -> None:
    op.execute('DROP POLICY IF EXISTS user_org_isolation ON "user"')
    op.drop_index("ix_user_org_id", table_name="user")
    op.drop_table("user")
    op.drop_table("org")
