"""store every timestamp with its time zone

Revision ID: c7e2a5f18b04
Revises: b4d9e1c7a2f5
Create Date: 2026-09-26 18:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'c7e2a5f18b04'
down_revision: str | None = 'b4d9e1c7a2f5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Every value already stored is UTC wall-clock time, since the database runs in
# UTC and the app only ever writes UTC. Without a zone on it the API sent it
# bare, and a browser in the Philippines read it as local time, eight hours off.
COLUMNS = [
    ('attachments', 'uploaded_at'),
    ('audit_log_entries', 'created_at'),
    ('notifications', 'created_at'),
    ('requests', 'classified_at'),
    ('requests', 'created_at'),
    ('requests', 'updated_at'),
    ('requests', 'resolved_at'),
    ('status_history_entries', 'created_at'),
    ('users', 'created_at'),
]


def upgrade() -> None:
    for table, column in COLUMNS:
        op.alter_column(
            table,
            column,
            type_=sa.DateTime(timezone=True),
            postgresql_using=f"{column} AT TIME ZONE 'UTC'",
        )


def downgrade() -> None:
    for table, column in COLUMNS:
        op.alter_column(
            table,
            column,
            type_=sa.DateTime(),
            postgresql_using=f"{column} AT TIME ZONE 'UTC'",
        )
