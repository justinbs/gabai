"""count failed sign-ins for the sign-in limit

Revision ID: f9b1d5e3a670
Revises: e7a9c3d1b248
Create Date: 2026-10-14 10:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'f9b1d5e3a670'
down_revision: str | None = 'e7a9c3d1b248'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # A counter, cleared as rows age out. The audit log keeps the record.
    op.create_table(
        'sign_in_failures',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_sign_in_failures_user_created', 'sign_in_failures', ['user_id', 'created_at'])
    op.create_index('ix_sign_in_failures_ip_created', 'sign_in_failures', ['ip_address', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_sign_in_failures_ip_created', table_name='sign_in_failures')
    op.drop_index('ix_sign_in_failures_user_created', table_name='sign_in_failures')
    op.drop_table('sign_in_failures')
