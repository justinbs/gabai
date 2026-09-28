"""add the columns retention works from

Revision ID: e8b3c6d41f72
Revises: d1a7f3c29e60
Create Date: 2026-09-28 10:30:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'e8b3c6d41f72'
down_revision: str | None = 'd1a7f3c29e60'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Retention counts from when an account was switched off, and nothing
    # recorded that except the audit log.
    op.add_column('users', sa.Column('deactivated_at', sa.DateTime(timezone=True), nullable=True))
    # Set once personal details are removed, so a second run skips the row and
    # anyone reading it can tell a removed account from a live one.
    op.add_column('users', sa.Column('anonymized_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('requests', sa.Column('redacted_at', sa.DateTime(timezone=True), nullable=True))

    # Accounts already switched off get the date from the audit log, so their
    # clock doesn't restart today. One with no entry stays null and is never
    # picked up; that is the safe side to be wrong on.
    op.execute(
        """
        UPDATE users u
        SET deactivated_at = a.at
        FROM (
            SELECT object_id, max(created_at) AS at
            FROM audit_log_entries
            WHERE action = 'user.deactivated'
            GROUP BY object_id
        ) a
        WHERE NOT u.is_active AND a.object_id = u.id::text
        """
    )


def downgrade() -> None:
    op.drop_column('requests', 'redacted_at')
    op.drop_column('users', 'anonymized_at')
    op.drop_column('users', 'deactivated_at')
