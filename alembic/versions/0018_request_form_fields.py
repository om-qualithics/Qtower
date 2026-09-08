"""Milestone 18 (Request forms as pages): tool_request gains data_tiers +
requires_enterprise_account, project_request gains data_tiers - new
questions specified in AI_Center_Technical_Handoff.md's "Request forms"
section. No vendor_request change - the open-source checklist expansion
is data (seed_vendor_checklist.py), not a schema change.

Revision ID: 0018
Revises: 0017
Create Date: 2026-09-02

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tool_request", sa.Column("data_tiers", postgresql.JSONB, nullable=False, server_default="[]")
    )
    op.add_column(
        "tool_request",
        sa.Column("requires_enterprise_account", sa.Boolean, nullable=False, server_default="false"),
    )
    op.add_column(
        "project_request", sa.Column("data_tiers", postgresql.JSONB, nullable=False, server_default="[]")
    )


def downgrade() -> None:
    op.drop_column("project_request", "data_tiers")
    op.drop_column("tool_request", "requires_enterprise_account")
    op.drop_column("tool_request", "data_tiers")
