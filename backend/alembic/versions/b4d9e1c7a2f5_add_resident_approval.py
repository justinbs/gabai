"""add resident approval to users

Revision ID: b4d9e1c7a2f5
Revises: 8c1f4e2a9d37
Create Date: 2026-09-26 12:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'b4d9e1c7a2f5'
down_revision: str | None = '8c1f4e2a9d37'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # VARCHAR plus CHECK rather than a native enum, per the schema deltas, so a
    # value can be added or dropped later without recreating a type.
    #
    # Accounts that exist now are already in use, so they're backfilled as
    # approved. The default then flips to pending for everything after.
    op.add_column(
        'users',
        sa.Column('approval_status', sa.String(length=10), server_default='approved', nullable=False),
    )
    op.create_check_constraint(
        'ck_users_approval_status',
        'users',
        "approval_status IN ('pending', 'approved', 'rejected')",
    )
    op.alter_column('users', 'approval_status', server_default='pending')
    op.add_column('users', sa.Column('residence', sa.String(length=150), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'residence')
    op.drop_constraint('ck_users_approval_status', 'users', type_='check')
    op.drop_column('users', 'approval_status')
