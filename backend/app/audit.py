import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLogEntry
from app.models.notification import Notification


async def write_audit(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    object_type: str,
    object_id: str | None = None,
    detail: dict | None = None,
    ip_address: str | None = None,
) -> None:
    db.add(
        AuditLogEntry(
            actor_id=actor_id,
            action=action,
            object_type=object_type,
            object_id=object_id,
            detail=detail,
            ip_address=ip_address,
        )
    )


async def notify(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    message: str,
    request_id: int | None = None,
    reference_number: str | None = None,
) -> None:
    db.add(
        Notification(
            user_id=user_id,
            request_id=request_id,
            reference_number=reference_number,
            message=message,
        )
    )