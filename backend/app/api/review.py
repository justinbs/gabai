from fastapi import APIRouter, Depends, Query
from sqlalchemy import func as sqlfunc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.enums import RequestStatus
from app.models.request import Request
from app.models.status_history import StatusHistoryEntry
from app.models.user import Role, User
from app.schemas.request import PaginatedRequests
from app.users import require_role

router = APIRouter(prefix="/api/review-queue", tags=["review"])


def _load_options():
    return (
        selectinload(Request.citizen),
        selectinload(Request.predicted_category),
        selectinload(Request.final_category),
        selectinload(Request.assigned_staff),
        selectinload(Request.status_history).selectinload(StatusHistoryEntry.actor),
    )


@router.get("", response_model=PaginatedRequests)
async def list_review_queue(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(Role.staff, Role.admin)),
):
    base_query = select(Request).where(Request.status == RequestStatus.under_review)

    total = (
        await db.execute(select(sqlfunc.count()).select_from(base_query.subquery()))
    ).scalar_one()

    query = (
        base_query.order_by(Request.created_at.asc())
        .offset(offset)
        .limit(limit)
        .options(*_load_options())
    )
    items = (await db.execute(query)).scalars().all()

    return PaginatedRequests(items=items, total=total, limit=limit, offset=offset)