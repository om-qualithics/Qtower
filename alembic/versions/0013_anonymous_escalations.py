"""Escalations become fully anonymous - drop reporter tracking

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-28

Anonymity is the whole point of Raise Alert per the product decision behind
this migration: nobody - not even an admin - should be able to trace an
escalation back to whoever raised it. reporter_id was a hard FK to user.id;
the only honest fix is to stop storing it at all, not just hide it in the
API/UI (a hidden-but-present column is one curl call away from de-anonymizing
every alert). code_scan_critical stays in the escalation_category enum type
(Postgres enum values can't be cheaply dropped, same constraint Milestone
5.1's status-enum migration ran into) but the application no longer ever
writes it - see codescan/tasks.py.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("escalation", "reporter_id")


def downgrade() -> None:
    # Downgrading can't recover who raised each existing alert - that data
    # is gone for good, by design. This just restores the column shape,
    # nullable (not the original NOT NULL) since there's nothing to
    # backfill it with.
    from sqlalchemy import Column
    from sqlalchemy.dialects.postgresql import UUID

    op.add_column("escalation", Column("reporter_id", UUID(as_uuid=True), nullable=True))
