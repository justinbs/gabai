"""record how staff verified a resident

Revision ID: c3e8a1f05d92
Revises: a6d2e9f41c30
Create Date: 2026-10-13 12:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'c3e8a1f05d92'
down_revision: str | None = 'a6d2e9f41c30'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

METHODS = ('id_in_person', 'personally_known', 'barangay_record')


def upgrade() -> None:
    # Residents approved before this stay NULL ("not recorded").
    op.add_column('users', sa.Column('verification_method', sa.String(length=20), nullable=True))
    op.create_check_constraint(
        'ck_users_verification_method',
        'users',
        "verification_method IS NULL OR verification_method IN ("
        + ", ".join(f"'{m}'" for m in METHODS)
        + ")",
    )


def downgrade() -> None:
    op.drop_constraint('ck_users_verification_method', 'users', type_='check')
    op.drop_column('users', 'verification_method')
