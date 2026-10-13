"""encrypt personal text at rest

Revision ID: a2c6e8f0b394
Revises: f9b1d5e3a670
Create Date: 2026-10-14 12:00:00.000000

Names, purok or street, request descriptions, status notes and attachment
file names already in the database are encrypted with the key in DATA_KEYS.
Status history refuses edits, so its protection is lifted only inside this
migration's transaction, and the change is written to the audit log.
"""
import json
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

from app.core import crypto
from app.core.markers import PLAIN_MARKERS


revision: str = 'a2c6e8f0b394'
down_revision: str | None = 'f9b1d5e3a670'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# table, column, original type to narrow back to on downgrade (None: was already text)
COLUMNS = (
    ('users', 'full_name', sa.String(length=150)),
    ('users', 'residence', sa.String(length=150)),
    ('requests', 'description', None),
    ('status_history_entries', 'note', None),
    ('attachments', 'filename', sa.String(length=255)),
)
TRIGGER = 'status_history_entries_no_rewrite'


def _convert(change) -> dict:
    conn = op.get_bind()
    counts = {}
    for table, column, _ in COLUMNS:
        rows = conn.execute(sa.text(f'SELECT id, {column} FROM {table} WHERE {column} IS NOT NULL')).all()
        done = 0
        for row_id, value in rows:
            new = change(value)
            if new != value:
                conn.execute(
                    sa.text(f'UPDATE {table} SET {column} = :value WHERE id = :id'),
                    {'value': new, 'id': row_id},
                )
                done += 1
        counts[f'{table}.{column}'] = done
    return counts


def _encrypt(value: str) -> str:
    if value in PLAIN_MARKERS or crypto.is_encrypted_text(value):
        return value
    return crypto.encrypt_text(value)


def _audit(action: str, counts: dict) -> None:
    op.get_bind().execute(
        sa.text(
            "INSERT INTO audit_log_entries (actor_id, action, object_type, object_id, detail, created_at) "
            "VALUES (NULL, :action, 'database', NULL, CAST(:detail AS jsonb), now())"
        ),
        {'action': action, 'detail': json.dumps(counts)},
    )


def upgrade() -> None:
    for table, column, _ in COLUMNS:
        op.alter_column(table, column, type_=sa.Text(), existing_nullable=True)
    op.execute(f'ALTER TABLE status_history_entries DISABLE TRIGGER {TRIGGER}')
    counts = _convert(_encrypt)
    op.execute(f'ALTER TABLE status_history_entries ENABLE TRIGGER {TRIGGER}')
    _audit('data.encrypted', counts)


def downgrade() -> None:
    op.execute(f'ALTER TABLE status_history_entries DISABLE TRIGGER {TRIGGER}')
    # Fails, and rolls back, if DATA_KEYS can't read a row, rather than writing garbage.
    counts = _convert(crypto.decrypt_text)
    op.execute(f'ALTER TABLE status_history_entries ENABLE TRIGGER {TRIGGER}')
    _audit('data.decrypted', counts)
    for table, column, original in COLUMNS:
        if original is not None:
            op.alter_column(table, column, type_=original, existing_nullable=True)
