"""resident urgent flag, and an index for the queue's waiting time

Revision ID: d4f2b7c9e016
Revises: c3e8a1f05d92
Create Date: 2026-10-13 14:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'd4f2b7c9e016'
down_revision: str | None = 'c3e8a1f05d92'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('requests', sa.Column('urgent_flagged_at', sa.DateTime(timezone=True), nullable=True))
    # Encrypted by the application, so plain text type.
    op.add_column('requests', sa.Column('urgent_reason', sa.Text(), nullable=True))
    # The queue sorts by each request's last status change.
    op.create_index(
        'ix_status_history_request_created',
        'status_history_entries',
        ['request_id', 'created_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_status_history_request_created', table_name='status_history_entries')
    op.drop_column('requests', 'urgent_reason')
    op.drop_column('requests', 'urgent_flagged_at')
