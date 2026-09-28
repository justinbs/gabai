"""Remove personal data that has outlived its purpose, as RA 10173 requires.

    python -m app.retention           # reports what it would do, changes nothing
    python -m app.retention --apply   # does it

Nothing runs until a period is set in .env (RETENTION_REQUEST_DAYS,
RETENTION_ACCOUNT_DAYS, RETENTION_IP_DAYS). The periods are the barangay's to
choose, not the code's, so the default is to keep everything.

This redacts rather than deletes. A finished request keeps its category,
urgency, status, reference number and timestamps, which is what reporting and
the audit trail need, and loses the resident's own words, the staff notes and
the attachments. A removed account keeps its id, so every log entry that names
it still points at a row, and loses its name, email and residence. No foreign key
is broken and neither log loses an entry: the append-only triggers allow exactly
the two changes made here.

Run it from cron, daily, after the backup (see scripts/backup.sh).
"""

import argparse
import asyncio
import secrets
from datetime import datetime, timedelta, timezone

from fastapi_users.password import PasswordHelper
from sqlalchemy import String, cast, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import write_audit
from app.core.config import get_settings
from app.core.eventloop import use_selector_loop_on_windows
from app.core.storage import UPLOAD_DIR
from app.db.session import AsyncSessionLocal
from app.models.attachment import Attachment
from app.models.audit_log import AuditLogEntry
from app.models.enums import RequestStatus
from app.models.notification import Notification
from app.models.request import Request
from app.models.status_history import StatusHistoryEntry
from app.models.user import ApprovalStatus, Role, User

settings = get_settings()

REDACTED_TEXT = "[Removed after the retention period]"
REMOVED_NAME = "Removed account"
FINISHED = (RequestStatus.resolved, RequestStatus.closed)


async def _redact_requests(db: AsyncSession, now: datetime, days: int) -> dict:
    cutoff = now - timedelta(days=days)
    finished_at = func.coalesce(Request.resolved_at, Request.updated_at)
    ids = (
        await db.execute(
            select(Request.id).where(
                Request.status.in_(FINISHED),
                Request.redacted_at.is_(None),
                finished_at < cutoff,
            )
        )
    ).scalars().all()
    if not ids:
        return {"requests": 0, "attachments": 0}

    attachments = (
        await db.execute(select(Attachment).where(Attachment.request_id.in_(ids)))
    ).scalars().all()
    for attachment in attachments:
        await db.delete(attachment)

    await db.execute(
        update(StatusHistoryEntry)
        .where(StatusHistoryEntry.request_id.in_(ids), StatusHistoryEntry.note.is_not(None))
        .values(note=REDACTED_TEXT)
    )
    await db.execute(
        update(Request)
        .where(Request.id.in_(ids))
        .values(description=REDACTED_TEXT, redacted_at=now)
    )
    # Files go after the rows are staged but are only removed once the caller
    # commits, see _remove_files.
    return {"requests": len(ids), "attachments": len(attachments), "_files": attachments}


async def _anonymize_accounts(db: AsyncSession, now: datetime, days: int) -> dict:
    cutoff = now - timedelta(days=days)

    last_rejected = (
        select(AuditLogEntry.object_id, func.max(AuditLogEntry.created_at).label("at"))
        .where(AuditLogEntry.action == "user.rejected")
        .group_by(AuditLogEntry.object_id)
        .subquery()
    )
    # A citizen with a request not yet redacted keeps their details until it is,
    # so a staff member never sees a live request from "Removed account".
    has_live_request = (
        select(Request.id)
        .where(Request.citizen_id == User.id, Request.redacted_at.is_(None))
        .exists()
    )
    deactivated = User.is_active.is_(False) & (User.deactivated_at < cutoff)
    rejected = (User.approval_status == ApprovalStatus.rejected) & (last_rejected.c.at < cutoff)

    users = (
        await db.execute(
            select(User)
            .outerjoin(last_rejected, last_rejected.c.object_id == cast(User.id, String))
            .where(
                # Staff and admin names stay: they are who acted in the audit
                # trail, and removing them removes the accountability.
                User.role == Role.citizen,
                User.anonymized_at.is_(None),
                deactivated | rejected,
                ~has_live_request,
            )
        )
    ).scalars().all()

    helper = PasswordHelper()
    for user in users:
        user.full_name = REMOVED_NAME
        user.email = f"removed-{user.id}@invalid"
        user.residence = None
        # Nobody knows this, so the account can never be signed into again.
        user.hashed_password = helper.hash(secrets.token_urlsafe(32))
        user.is_active = False
        user.is_verified = False
        user.anonymized_at = now

    if users:
        await db.execute(
            Notification.__table__.delete().where(
                Notification.user_id.in_([u.id for u in users])
            )
        )
    return {"accounts": len(users)}


async def _clear_ips(db: AsyncSession, now: datetime, days: int) -> dict:
    cutoff = now - timedelta(days=days)
    result = await db.execute(
        update(AuditLogEntry)
        .where(AuditLogEntry.created_at < cutoff, AuditLogEntry.ip_address.is_not(None))
        .values(ip_address=None)
    )
    return {"ip_addresses": result.rowcount}


def _remove_files(attachments: list[Attachment]) -> None:
    for attachment in attachments:
        (UPLOAD_DIR / attachment.stored_path).unlink(missing_ok=True)


async def run(apply: bool) -> dict:
    now = datetime.now(timezone.utc)
    report: dict = {}
    files: list[Attachment] = []

    async with AsyncSessionLocal() as db:
        if settings.retention_request_days is not None:
            counts = await _redact_requests(db, now, settings.retention_request_days)
            files = counts.pop("_files", [])
            report.update(counts)
        if settings.retention_account_days is not None:
            report.update(await _anonymize_accounts(db, now, settings.retention_account_days))
        if settings.retention_ip_days is not None:
            report.update(await _clear_ips(db, now, settings.retention_ip_days))

        if not report:
            print("No retention period is set, so nothing was checked. See .env.example.")
            return report

        if not apply:
            await db.rollback()
            print(f"Dry run, nothing changed. Would remove: {report}")
            print("Run again with --apply to do it.")
            return report

        if not any(report.values()):
            # A daily run that finds nothing leaves no entry, or the audit log
            # fills with empty ones.
            print("Nothing is past its retention period.")
            return report

        await write_audit(
            db,
            actor_id=None,
            action="retention.applied",
            object_type="system",
            detail={
                **report,
                "request_days": settings.retention_request_days,
                "account_days": settings.retention_account_days,
                "ip_days": settings.retention_ip_days,
            },
        )
        await db.commit()

    # Only after the commit. A crash before it leaves the rows and their files
    # both in place; after it, at worst an orphaned file, never a row pointing
    # at a file that is gone.
    _remove_files(files)
    print(f"Removed: {report}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="make the changes")
    args = parser.parse_args()
    asyncio.run(run(args.apply))


if __name__ == "__main__":
    use_selector_loop_on_windows()
    main()
