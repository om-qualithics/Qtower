"""Milestone 17 (Logos): approved_tool.logo_url (vendor.logo_url already
exists from migration 0014, no change needed there).

Revision ID: 0017
Revises: 0016
Create Date: 2026-09-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("approved_tool", sa.Column("logo_url", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("approved_tool", "logo_url")
