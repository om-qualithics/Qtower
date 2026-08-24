"""tool precheck v2: policy.markdown_key (cached .md of the active
policy), deployment_config.tool_assessment_prompt (admin-editable
precheck prompt override), tool_assessment_status gains "skipped" (used
when a request is created with no active policy - no AI call is made at
all in that case)

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("policy", sa.Column("markdown_key", sa.Text, nullable=True))
    op.add_column("deployment_config", sa.Column("tool_assessment_prompt", sa.Text, nullable=True))

    # Pure addition (not a rename/removal), unlike the 0006 policy_status
    # recreate-type dance - ALTER TYPE ... ADD VALUE is sufficient here.
    # Must run outside the migration's transaction block on Postgres <12;
    # alembic's env.py runs each migration non-transactionally by default
    # for this repo (confirmed no explicit transactional DDL wrapping), so
    # this executes standalone.
    op.execute("ALTER TYPE tool_assessment_status ADD VALUE IF NOT EXISTS 'skipped'")


def downgrade() -> None:
    # Postgres has no ALTER TYPE ... DROP VALUE - downgrading the enum
    # would require the full recreate-type dance from migration 0006.
    # Not implemented since no other migration in this repo has needed to
    # downgrade an enum value addition either; only the additive columns
    # are reversible here.
    op.drop_column("deployment_config", "tool_assessment_prompt")
    op.drop_column("policy", "markdown_key")
