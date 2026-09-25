"""add must_change_password to users

Revision ID: 8c1f4e2a9d37
Revises: 535261a5a068
Create Date: 2026-09-24 10:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '8c1f4e2a9d37'
down_revision: str | None = '535261a5a068'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing accounts start cleared. That includes any an admin made before
    # this change, which are not backfilled.
    op.add_column(
        'users',
        sa.Column('must_change_password', sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column('users', 'must_change_password')
