"""policy lifecycle: draft/active/archived, source, approval audit fields

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Postgres enums can't have a value removed/renamed via ALTER TYPE ...
    # ADD VALUE cleanly, so swap in a new type: create it, convert the
    # column with a USING clause (old "generated" -> "draft" - a
    # generated-but-never-approved policy is just a draft with a document
    # attached in the new model), drop the old type, rename the new one in.
    op.execute("CREATE TYPE policy_status_new AS ENUM ('draft', 'active', 'archived')")
    op.execute("ALTER TABLE \"policy\" ALTER COLUMN status DROP DEFAULT")
    op.execute(
        """
        ALTER TABLE "policy" ALTER COLUMN status TYPE policy_status_new
        USING (CASE status::text WHEN 'generated' THEN 'draft' ELSE status::text END)::policy_status_new
        """
    )
    op.execute("ALTER TABLE \"policy\" ALTER COLUMN status SET DEFAULT 'draft'")
    op.execute("DROP TYPE policy_status")
    op.execute("ALTER TYPE policy_status_new RENAME TO policy_status")

    policy_source = postgresql.ENUM("builder", "upload", name="policy_source", create_type=False)
    policy_source.create(op.get_bind(), checkfirst=True)
    op.add_column("policy", sa.Column("source", policy_source, nullable=False, server_default="builder"))

    op.add_column("policy", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("policy", sa.Column("approved_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=True))

    op.execute("ALTER TABLE \"policy\" ALTER COLUMN version SET DEFAULT 0")

    # Hard DB-level invariant: at most one active policy per org.
    op.execute(
        """
        CREATE UNIQUE INDEX ix_policy_one_active_per_org
        ON "policy" (org_id)
        WHERE status = 'active'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_policy_one_active_per_org")
    op.execute("ALTER TABLE \"policy\" ALTER COLUMN version SET DEFAULT 1")
    op.drop_column("policy", "approved_by")
    op.drop_column("policy", "approved_at")
    op.drop_column("policy", "source")
    op.execute("DROP TYPE IF EXISTS policy_source")

    op.execute("CREATE TYPE policy_status_old AS ENUM ('draft', 'generated')")
    op.execute("ALTER TABLE \"policy\" ALTER COLUMN status DROP DEFAULT")
    op.execute(
        """
        ALTER TABLE "policy" ALTER COLUMN status TYPE policy_status_old
        USING (CASE status::text WHEN 'active' THEN 'generated' WHEN 'archived' THEN 'generated' ELSE status::text END)::policy_status_old
        """
    )
    op.execute("ALTER TABLE \"policy\" ALTER COLUMN status SET DEFAULT 'draft'")
    op.execute("DROP TYPE policy_status")
    op.execute("ALTER TYPE policy_status_old RENAME TO policy_status")
