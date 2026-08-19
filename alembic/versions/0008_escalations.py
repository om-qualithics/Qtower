"""escalations: escalation table, notification_log, branding override field

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    notification_status = postgresql.ENUM("sent", "failed", name="notification_status")
    notification_status.create(op.get_bind(), checkfirst=True)
    notification_status_nc = postgresql.ENUM("sent", "failed", name="notification_status", create_type=False)

    op.create_table(
        "notification_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("org.id"), nullable=True),
        sa.Column("to_emails", postgresql.JSONB, nullable=False),
        sa.Column("subject", sa.Text, nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("status", notification_status_nc, nullable=False),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_notification_log_org_id", "notification_log", ["org_id"])
    op.execute('ALTER TABLE "notification_log" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "notification_log" FORCE ROW LEVEL SECURITY')
    op.execute(
        """
        CREATE POLICY notification_log_org_isolation ON "notification_log"
        USING (org_id = current_setting('app.current_org_id', true)::uuid)
        WITH CHECK (org_id = current_setting('app.current_org_id', true)::uuid)
        """
    )

    escalation_category = postgresql.ENUM(
        "policy_violation", "unapproved_tool_use", "data_exposure_concern", "other", name="escalation_category"
    )
    escalation_category.create(op.get_bind(), checkfirst=True)
    escalation_category_nc = postgresql.ENUM(
        "policy_violation",
        "unapproved_tool_use",
        "data_exposure_concern",
        "other",
        name="escalation_category",
        create_type=False,
    )
    escalation_status = postgresql.ENUM("open", "in_review", "resolved", name="escalation_status")
    escalation_status.create(op.get_bind(), checkfirst=True)
    escalation_status_nc = postgresql.ENUM("open", "in_review", "resolved", name="escalation_status", create_type=False)

    op.create_table(
        "escalation",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("org.id"), nullable=False),
        sa.Column("reporter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("category", escalation_category_nc, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("related_tool_request_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tool_request.id"), nullable=True),
        sa.Column("related_policy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("policy.id"), nullable=True),
        sa.Column("status", escalation_status_nc, nullable=False, server_default="open"),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("resolution_note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_escalation_org_id", "escalation", ["org_id"])
    op.execute('ALTER TABLE "escalation" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "escalation" FORCE ROW LEVEL SECURITY')
    op.execute(
        """
        CREATE POLICY escalation_org_isolation ON "escalation"
        USING (org_id = current_setting('app.current_org_id', true)::uuid)
        WITH CHECK (org_id = current_setting('app.current_org_id', true)::uuid)
        """
    )

    op.add_column("deployment_config", sa.Column("escalation_notify_override_email", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("deployment_config", "escalation_notify_override_email")

    op.execute('DROP POLICY IF EXISTS escalation_org_isolation ON "escalation"')
    op.drop_index("ix_escalation_org_id", table_name="escalation")
    op.drop_table("escalation")
    postgresql.ENUM(name="escalation_status").drop(op.get_bind())
    postgresql.ENUM(name="escalation_category").drop(op.get_bind())

    op.execute('DROP POLICY IF EXISTS notification_log_org_isolation ON "notification_log"')
    op.drop_index("ix_notification_log_org_id", table_name="notification_log")
    op.drop_table("notification_log")
    postgresql.ENUM(name="notification_status").drop(op.get_bind())
