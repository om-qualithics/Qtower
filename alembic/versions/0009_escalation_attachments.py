"""escalation attachments: attachment_key/attachment_filename columns

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("escalation", sa.Column("attachment_key", sa.Text, nullable=True))
    op.add_column("escalation", sa.Column("attachment_filename", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("escalation", "attachment_filename")
    op.drop_column("escalation", "attachment_key")
