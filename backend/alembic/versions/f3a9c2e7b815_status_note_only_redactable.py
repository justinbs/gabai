"""status history: a note may only be cleared or redacted, not rewritten

Revision ID: f3a9c2e7b815
Revises: e8b3c6d41f72
Create Date: 2026-09-29 12:00:00.000000

"""
from collections.abc import Sequence

from alembic import op


revision: str = 'f3a9c2e7b815'
down_revision: str | None = 'e8b3c6d41f72'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The append-only trigger locked every column of a status history row except the
# note, which it let change to anything. Retention only ever needs to replace a
# note with its removal marker (app/retention.py REDACTED_TEXT), so allow that,
# clearing it, or leaving it alone, and refuse any other rewrite.
MARKER = "[Removed after the retention period]"

STRICT = f"""
CREATE OR REPLACE FUNCTION status_history_entries_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE'
       AND (NEW.id, NEW.request_id, NEW.from_status, NEW.to_status,
            NEW.actor_id, NEW.created_at)
           IS NOT DISTINCT FROM
           (OLD.id, OLD.request_id, OLD.from_status, OLD.to_status,
            OLD.actor_id, OLD.created_at)
       AND (NEW.note IS NOT DISTINCT FROM OLD.note
            OR NEW.note IS NULL
            OR NEW.note = '{MARKER}')
    THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'status_history_entries is append-only: % refused', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END;
$$;
"""

# The version d1a7f3c29e60 created, restored on downgrade.
PREVIOUS = """
CREATE OR REPLACE FUNCTION status_history_entries_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE'
       AND (NEW.id, NEW.request_id, NEW.from_status, NEW.to_status,
            NEW.actor_id, NEW.created_at)
           IS NOT DISTINCT FROM
           (OLD.id, OLD.request_id, OLD.from_status, OLD.to_status,
            OLD.actor_id, OLD.created_at)
    THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'status_history_entries is append-only: % refused', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END;
$$;
"""


def upgrade() -> None:
    op.execute(STRICT)


def downgrade() -> None:
    op.execute(PREVIOUS)
