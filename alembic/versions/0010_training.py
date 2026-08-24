"""training: training_module (shared catalog, no org_id/RLS) and
training_completion (org-scoped, RLS)

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    video_type = postgresql.ENUM("placeholder", "file", "embed", name="training_video_type")
    video_type.create(op.get_bind(), checkfirst=True)
    video_type_nc = postgresql.ENUM("placeholder", "file", "embed", name="training_video_type", create_type=False)

    completion_status = postgresql.ENUM(
        "not_started", "in_progress", "completed", name="training_completion_status"
    )
    completion_status.create(op.get_bind(), checkfirst=True)
    completion_status_nc = postgresql.ENUM(
        "not_started", "in_progress", "completed", name="training_completion_status", create_type=False
    )

    # No org_id, no RLS - deliberate, see training/models.py's docstring.
    # This is the shared curriculum, identical across every org.
    op.create_table(
        "training_module",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_index", sa.Integer, nullable=False),
        sa.Column("key", sa.Text, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("body_text", sa.Text, nullable=False),
        sa.Column("video_type", video_type_nc, nullable=False, server_default="placeholder"),
        sa.Column("video_url", sa.Text, nullable=True),
        sa.Column("questions", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint("uq_training_module_order_index", "training_module", ["order_index"])
    op.create_unique_constraint("uq_training_module_key", "training_module", ["key"])

    op.create_table(
        "training_completion",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("org.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("module_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("training_module.id"), nullable=False),
        sa.Column("status", completion_status_nc, nullable=False, server_default="not_started"),
        sa.Column("answers", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_training_completion_org_id", "training_completion", ["org_id"])
    op.create_unique_constraint(
        "uq_training_completion_org_user_module", "training_completion", ["org_id", "user_id", "module_id"]
    )
    op.execute('ALTER TABLE "training_completion" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "training_completion" FORCE ROW LEVEL SECURITY')
    op.execute(
        """
        CREATE POLICY training_completion_org_isolation ON "training_completion"
        USING (org_id = current_setting('app.current_org_id', true)::uuid)
        WITH CHECK (org_id = current_setting('app.current_org_id', true)::uuid)
        """
    )


def downgrade() -> None:
    op.execute('DROP POLICY IF EXISTS training_completion_org_isolation ON "training_completion"')
    op.drop_index("ix_training_completion_org_id", table_name="training_completion")
    op.drop_table("training_completion")
    postgresql.ENUM(name="training_completion_status").drop(op.get_bind())

    op.drop_table("training_module")
    postgresql.ENUM(name="training_video_type").drop(op.get_bind())
