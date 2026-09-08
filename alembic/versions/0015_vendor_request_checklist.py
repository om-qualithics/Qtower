"""vendor register: request-time checklist answers. The requester now
answers the checklist directly on the request (not left for govern/assure
to fill in after approval) - vendor_request gains a computed
projected_status/overall_score (same scoring.score_vendor() logic used
for an approved vendor), and vendor_request_checklist_response mirrors
vendor_checklist_response's shape for the request's own answers, copied
over to real vendor_checklist_response rows on approval.

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015"
down_revision: Union[str, None] = "0014"
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
    vendor_status_nc = postgresql.ENUM(
        "approved", "needs_review", "restricted", "pending", name="vendor_status", create_type=False
    )
    checklist_answer_nc = postgresql.ENUM(
        "yes", "no", "partial", "not_applicable", name="vendor_checklist_answer", create_type=False
    )

    op.add_column("vendor_request", sa.Column("projected_status", vendor_status_nc, nullable=True))
    op.add_column("vendor_request", sa.Column("overall_score", sa.Numeric, nullable=True))

    op.create_table(
        "vendor_request_checklist_response",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("org.id"), nullable=False),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vendor_request.id"), nullable=False),
        sa.Column(
            "checklist_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vendor_checklist_item.id"), nullable=False
        ),
        sa.Column("answer", checklist_answer_nc, nullable=False),
        sa.Column("evidence_note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_vendor_request_checklist_response_org_id", "vendor_request_checklist_response", ["org_id"]
    )
    op.create_unique_constraint(
        "uq_vendor_request_checklist_response_request_item",
        "vendor_request_checklist_response",
        ["request_id", "checklist_item_id"],
    )
    _rls("vendor_request_checklist_response", "vendor_request_checklist_response_org_isolation")


def downgrade() -> None:
    op.execute(
        'DROP POLICY IF EXISTS vendor_request_checklist_response_org_isolation ON "vendor_request_checklist_response"'
    )
    op.drop_index("ix_vendor_request_checklist_response_org_id", table_name="vendor_request_checklist_response")
    op.drop_table("vendor_request_checklist_response")

    op.drop_column("vendor_request", "overall_score")
    op.drop_column("vendor_request", "projected_status")
