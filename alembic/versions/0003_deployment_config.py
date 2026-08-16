"""deployment_config (branding + license, one table per handoff §5 sketch)

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "deployment_config",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("org.id"), nullable=False, unique=True),
        sa.Column("org_display_name", sa.String(255), nullable=True),
        sa.Column("logo_url", sa.String(1024), nullable=True),
        sa.Column("primary_color", sa.String(32), nullable=True),
        sa.Column("secondary_color", sa.String(32), nullable=True),
        sa.Column("email_templates", postgresql.JSONB, nullable=True),
        sa.Column("license_token", sa.Text, nullable=True),
        sa.Column("license_seat_count", sa.Integer, nullable=True),
        sa.Column("license_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enabled_feature_modules", postgresql.JSONB, nullable=True),
        sa.Column("license_valid", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("license_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.execute('ALTER TABLE "deployment_config" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "deployment_config" FORCE ROW LEVEL SECURITY')
    op.execute(
        """
        CREATE POLICY deployment_config_org_isolation ON "deployment_config"
        USING (org_id = current_setting('app.current_org_id', true)::uuid)
        WITH CHECK (org_id = current_setting('app.current_org_id', true)::uuid)
        """
    )


def downgrade() -> None:
    op.execute('DROP POLICY IF EXISTS deployment_config_org_isolation ON "deployment_config"')
    op.drop_table("deployment_config")
