import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func as sqlfunc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.audit_log import AuditLogEntry
from app.models.user import Role, User
from app.schemas.audit import PaginatedAuditLog
from app.users import require_role

router = APIRouter(prefix="/api/admin/audit-log", tags=["admin"])


@router.get("", response_model=PaginatedAuditLog)
async def list_audit_log(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    actor_id: uuid.UUID | None = Query(None),
    action: str | None = Query(None, max_length=100),
    object_type: str | None = Query(None, max_length=50),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_role(Role.admin)),
):
    query = select(AuditLogEntry)
    if actor_id:
        query = query.where(AuditLogEntry.actor_id == actor_id)
    if action:
        query = query.where(AuditLogEntry.action == action)
    if object_type:
        query = query.where(AuditLogEntry.object_type == object_type)
    if date_from:
        query = query.where(AuditLogEntry.created_at >= date_from)
    if date_to:
        query = query.where(AuditLogEntry.created_at <= date_to)

    total = (
        await db.execute(select(sqlfunc.count()).select_from(query.subquery()))
    ).scalar_one()

    query = (
        query.order_by(AuditLogEntry.created_at.desc())
        .offset(offset)
        .limit(limit)
        .options(selectinload(AuditLogEntry.actor))
    )
    items = (await db.execute(query)).scalars().all()

    return PaginatedAuditLog(items=items, total=total, limit=limit, offset=offset)