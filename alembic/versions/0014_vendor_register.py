"""vendor register: vendor/vendor_request (circular FK, RLS), shared
vendor_checklist_item catalog (no org_id/RLS, same precedent as
training_module), vendor_checklist_response (RLS). See
AI_Center_Technical_Handoff.md / the build plan's Milestone 14 for the
scoring-service design this schema supports.

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _rls(table: str, policy: str) -> None:
    # Same false-positive shape as 0012_codescan.py's _rls() - table/policy
    # are always hardcoded literals at the call sites below, never traced
    # back to user input.
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
    vendor_type = postgresql.ENUM("commercial", "open_source", name="vendor_type")
    vendor_type.create(op.get_bind(), checkfirst=True)
    vendor_type_nc = postgresql.ENUM("commercial", "open_source", name="vendor_type", create_type=False)

    vendor_status = postgresql.ENUM("approved", "needs_review", "restricted", "pending", name="vendor_status")
    vendor_status.create(op.get_bind(), checkfirst=True)
    vendor_status_nc = postgresql.ENUM(
        "approved", "needs_review", "restricted", "pending", name="vendor_status", create_type=False
    )

    vendor_request_status = postgresql.ENUM("pending", "approved", "rejected", name="vendor_request_status")
    vendor_request_status.create(op.get_bind(), checkfirst=True)
    vendor_request_status_nc = postgresql.ENUM(
        "pending", "approved", "rejected", name="vendor_request_status", create_type=False
    )

    checklist_tier = postgresql.ENUM("must_have", "good_to_have", "optional", name="vendor_checklist_tier")
    checklist_tier.create(op.get_bind(), checkfirst=True)
    checklist_tier_nc = postgresql.ENUM(
        "must_have", "good_to_have", "optional", name="vendor_checklist_tier", create_type=False
    )

    checklist_applies_to = postgresql.ENUM(
        "commercial", "open_source", "both", name="vendor_checklist_applies_to"
    )
    checklist_applies_to.create(op.get_bind(), checkfirst=True)
    checklist_applies_to_nc = postgresql.ENUM(
        "commercial", "open_source", "both", name="vendor_checklist_applies_to", create_type=False
    )

    checklist_answer = postgresql.ENUM("yes", "no", "partial", "not_applicable", name="vendor_checklist_answer")
    checklist_answer.create(op.get_bind(), checkfirst=True)
    checklist_answer_nc = postgresql.ENUM(
        "yes", "no", "partial", "not_applicable", name="vendor_checklist_answer", create_type=False
    )

    # vendor_request is created first with resulting_vendor_id as a plain
    # column (no FK yet) - vendor doesn't exist yet and the two tables
    # reference each other, same sequencing as tool_request/approved_tool
    # in 0007_tools.py.
    op.create_table(
        "vendor_request",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("org.id"), nullable=False),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("type", vendor_type_nc, nullable=False),
        sa.Column("website_url", sa.Text, nullable=True),
        sa.Column("business_justification", sa.Text, nullable=False),
        sa.Column("resulting_vendor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", vendor_request_status_nc, nullable=False, server_default="pending"),
        sa.Column("decided_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_vendor_request_org_id", "vendor_request", ["org_id"])
    _rls("vendor_request", "vendor_request_org_isolation")

    op.create_table(
        "vendor",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("org.id"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("type", vendor_type_nc, nullable=False),
        sa.Column("category", sa.Text, nullable=True),
        sa.Column("logo_url", sa.Text, nullable=True),
        sa.Column("website_url", sa.Text, nullable=True),
        sa.Column("status", vendor_status_nc, nullable=False, server_default="pending"),
        sa.Column("overall_score", sa.Numeric, nullable=True),
        sa.Column(
            "created_from_request_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vendor_request.id"), nullable=True
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_vendor_org_id", "vendor", ["org_id"])
    _rls("vendor", "vendor_org_isolation")

    op.create_foreign_key(
        "fk_vendor_request_resulting_vendor",
        "vendor_request",
        "vendor",
        ["resulting_vendor_id"],
        ["id"],
    )

    # No org_id, no RLS - shared reference catalog, same precedent as
    # training_module (see training/models.py's docstring).
    op.create_table(
        "vendor_checklist_item",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.Text, nullable=False),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("tier", checklist_tier_nc, nullable=False),
        sa.Column("applies_to", checklist_applies_to_nc, nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False),
    )
    op.create_unique_constraint("uq_vendor_checklist_item_key", "vendor_checklist_item", ["key"])

    op.create_table(
        "vendor_checklist_response",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("org.id"), nullable=False),
        sa.Column("vendor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vendor.id"), nullable=False),
        sa.Column(
            "checklist_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vendor_checklist_item.id"), nullable=False
        ),
        sa.Column("answer", checklist_answer_nc, nullable=False),
        sa.Column("evidence_note", sa.Text, nullable=True),
        sa.Column("last_verified_date", sa.Date, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_vendor_checklist_response_org_id", "vendor_checklist_response", ["org_id"])
    op.create_unique_constraint(
        "uq_vendor_checklist_response_vendor_item",
        "vendor_checklist_response",
        ["vendor_id", "checklist_item_id"],
    )
    _rls("vendor_checklist_response", "vendor_checklist_response_org_isolation")


def downgrade() -> None:
    op.execute('DROP POLICY IF EXISTS vendor_checklist_response_org_isolation ON "vendor_checklist_response"')
    op.drop_index("ix_vendor_checklist_response_org_id", table_name="vendor_checklist_response")
    op.drop_table("vendor_checklist_response")
    postgresql.ENUM(name="vendor_checklist_answer").drop(op.get_bind())

    op.drop_table("vendor_checklist_item")
    postgresql.ENUM(name="vendor_checklist_applies_to").drop(op.get_bind())
    postgresql.ENUM(name="vendor_checklist_tier").drop(op.get_bind())

    op.drop_constraint("fk_vendor_request_resulting_vendor", "vendor_request", type_="foreignkey")

    op.execute('DROP POLICY IF EXISTS vendor_org_isolation ON "vendor"')
    op.drop_index("ix_vendor_org_id", table_name="vendor")
    op.drop_table("vendor")
    postgresql.ENUM(name="vendor_status").drop(op.get_bind())

    op.execute('DROP POLICY IF EXISTS vendor_request_org_isolation ON "vendor_request"')
    op.drop_index("ix_vendor_request_org_id", table_name="vendor_request")
    op.drop_table("vendor_request")
    postgresql.ENUM(name="vendor_request_status").drop(op.get_bind())
    postgresql.ENUM(name="vendor_type").drop(op.get_bind())
