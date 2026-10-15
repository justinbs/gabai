"""when staff first acted on a request the resident marked urgent

Revision ID: b5d8f2a4c716
Revises: a2c6e8f0b394
Create Date: 2026-10-13 22:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'b5d8f2a4c716'
down_revision: str | None = 'a2c6e8f0b394'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('requests', sa.Column('urgent_seen_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('requests', 'urgent_seen_at')
