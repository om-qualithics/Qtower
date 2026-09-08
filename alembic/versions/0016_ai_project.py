"""AI Project (Milestone 16): project/project_request (circular FK, RLS,
same tool_request/approved_tool sequencing), project_tool_link/
project_vendor_link (many-to-many join rows, org_id + RLS - each row
points at exactly one of a real catalog entry or a free-text "other"
name, and exactly one of project_id/request_id, both enforced at the
service layer, not a DB constraint, matching this codebase's existing
preference). Reuses tool_request_status/tool_assessment_status/
tool_assessment_result (create_type=False) rather than defining new
enums with identical values - project assessment follows the exact same
skip-if-no-active-policy / never-auto-approve contract tool assessment
already established. Also adds deployment_config.project_assessment_prompt
(admin-editable precheck prompt override, same shape as
tool_assessment_prompt - not yet exposed via a Settings UI section in
this milestone, curl/API-editable via the existing PATCH /branding/config
generic update).

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _rls(table: str, policy: str) -> None:
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
    op.add_column("deployment_config", sa.Column("project_assessment_prompt", sa.Text, nullable=True))

    lifecycle_stage = postgresql.ENUM("idea", "pilot", "production", "retired", name="project_lifecycle_stage")
    lifecycle_stage.create(op.get_bind(), checkfirst=True)
    lifecycle_stage_nc = postgresql.ENUM(
        "idea", "pilot", "production", "retired", name="project_lifecycle_stage", create_type=False
    )

    # Reused as-is (create_type=False) - identical value sets to what
    # tools/models.py already defined, no reason to duplicate the type.
    request_status_nc = postgresql.ENUM("pending", "approved", "rejected", name="tool_request_status", create_type=False)
    assessment_status_nc = postgresql.ENUM(
        "pending", "complete", "failed", "skipped", name="tool_assessment_status", create_type=False
    )
    assessment_result_nc = postgresql.ENUM(
        "approvable", "needs_review", "cannot_approve", name="tool_assessment_result", create_type=False
    )

    # project_request is created first with resulting_project_id as a
    # plain column (no FK yet) - project doesn't exist yet and the two
    # tables reference each other, same sequencing as tool_request/
    # approved_tool in 0007_tools.py.
    op.create_table(
        "project_request",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("org.id"), nullable=False),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("business_justification", sa.Text, nullable=False),
        sa.Column("data_flow_description", sa.Text, nullable=False),
        sa.Column("human_in_loop", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("status", request_status_nc, nullable=False, server_default="pending"),
        sa.Column("project_assessment_status", assessment_status_nc, nullable=False, server_default="pending"),
        sa.Column("project_assessment_result", assessment_result_nc, nullable=True),
        sa.Column("project_assessment_explanation", sa.Text, nullable=True),
        sa.Column("resulting_project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decided_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_project_request_org_id", "project_request", ["org_id"])
    _rls("project_request", "project_request_org_isolation")

    op.create_table(
        "project",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("org.id"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("lifecycle_stage", lifecycle_stage_nc, nullable=False, server_default="idea"),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=True),
        sa.Column(
            "created_from_request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("project_request.id"),
            nullable=True,
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_project_org_id", "project", ["org_id"])
    _rls("project", "project_org_isolation")

    op.create_foreign_key(
        "fk_project_request_resulting_project",
        "project_request",
        "project",
        ["resulting_project_id"],
        ["id"],
    )

    # Exactly one of project_id/request_id is set (which "owner" a link
    # row belongs to - a request's proposed links before approval, or a
    # real project's links after) and exactly one of tool_id/other_name
    # is set (a real catalog entry vs. a free-text "not registered in
    # inventory" name) - both invariants enforced in service.py, not a DB
    # CHECK constraint, matching this schema's existing preference for
    # service-layer validation.
    op.create_table(
        "project_tool_link",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("org.id"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("project.id"), nullable=True),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("project_request.id"), nullable=True),
        sa.Column("tool_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("approved_tool.id"), nullable=True),
        sa.Column("other_name", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_project_tool_link_org_id", "project_tool_link", ["org_id"])
    _rls("project_tool_link", "project_tool_link_org_isolation")

    op.create_table(
        "project_vendor_link",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("org.id"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("project.id"), nullable=True),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("project_request.id"), nullable=True),
        sa.Column("vendor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vendor.id"), nullable=True),
        sa.Column("other_name", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_project_vendor_link_org_id", "project_vendor_link", ["org_id"])
    _rls("project_vendor_link", "project_vendor_link_org_isolation")


def downgrade() -> None:
    op.execute('DROP POLICY IF EXISTS project_vendor_link_org_isolation ON "project_vendor_link"')
    op.drop_index("ix_project_vendor_link_org_id", table_name="project_vendor_link")
    op.drop_table("project_vendor_link")

    op.execute('DROP POLICY IF EXISTS project_tool_link_org_isolation ON "project_tool_link"')
    op.drop_index("ix_project_tool_link_org_id", table_name="project_tool_link")
    op.drop_table("project_tool_link")

    op.drop_constraint("fk_project_request_resulting_project", "project_request", type_="foreignkey")

    op.execute('DROP POLICY IF EXISTS project_org_isolation ON "project"')
    op.drop_index("ix_project_org_id", table_name="project")
    op.drop_table("project")
    postgresql.ENUM(name="project_lifecycle_stage").drop(op.get_bind())

    op.execute('DROP POLICY IF EXISTS project_request_org_isolation ON "project_request"')
    op.drop_index("ix_project_request_org_id", table_name="project_request")
    op.drop_table("project_request")

    op.drop_column("deployment_config", "project_assessment_prompt")
