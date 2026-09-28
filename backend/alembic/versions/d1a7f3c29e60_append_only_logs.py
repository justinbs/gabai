"""make the audit log and status history append-only

Revision ID: d1a7f3c29e60
Revises: c7e2a5f18b04
Create Date: 2026-09-28 10:00:00.000000

"""
from collections.abc import Sequence

from alembic import op


revision: str = 'd1a7f3c29e60'
down_revision: str | None = 'c7e2a5f18b04'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The API never edits or deletes either log, but that only holds for code that
# goes through the API. These triggers make the database refuse it too, so a
# stray script or someone at a psql prompt can't quietly rewrite history.
#
# Each allows exactly one change, the one retention needs (app/retention.py):
# clearing an audit entry's IP address, and blanking a status note. Everything
# else about a row stays as written. A superuser can still disable a trigger,
# but that is a deliberate act, not an accident.

AUDIT_FUNCTION = """
CREATE FUNCTION audit_log_entries_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE'
       AND NEW.ip_address IS NULL
       AND (NEW.id, NEW.actor_id, NEW.action, NEW.object_type, NEW.object_id,
            NEW.detail, NEW.created_at)
           IS NOT DISTINCT FROM
           (OLD.id, OLD.actor_id, OLD.action, OLD.object_type, OLD.object_id,
            OLD.detail, OLD.created_at)
    THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'audit_log_entries is append-only: % refused', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END;
$$;
"""

HISTORY_FUNCTION = """
CREATE FUNCTION status_history_entries_append_only() RETURNS trigger
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

TABLES = ("audit_log_entries", "status_history_entries")


def upgrade() -> None:
    op.execute(AUDIT_FUNCTION)
    op.execute(HISTORY_FUNCTION)
    for table in TABLES:
        op.execute(
            f"CREATE TRIGGER {table}_no_rewrite BEFORE UPDATE OR DELETE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION {table}_append_only()"
        )
        # Row triggers don't fire on TRUNCATE, so it needs its own.
        op.execute(
            f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
            f"FOR EACH STATEMENT EXECUTE FUNCTION {table}_append_only()"
        )


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"DROP TRIGGER {table}_no_truncate ON {table}")
        op.execute(f"DROP TRIGGER {table}_no_rewrite ON {table}")
        op.execute(f"DROP FUNCTION {table}_append_only()")
