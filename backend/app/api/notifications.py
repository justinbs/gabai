from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from sqlalchemy import func as sqlfunc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import NotificationRead, PaginatedNotifications
from app.users import current_active_user

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=PaginatedNotifications)
async def list_notifications(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    unread_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_active_user),
):
    query = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        query = query.where(Notification.is_read.is_(False))

    total = (
        await db.execute(select(sqlfunc.count()).select_from(query.subquery()))
    ).scalar_one()
    unread_count = (
        await db.execute(
            select(sqlfunc.count()).select_from(
                select(Notification)
                .where(Notification.user_id == user.id, Notification.is_read.is_(False))
                .subquery()
            )
        )
    ).scalar_one()

    query = query.order_by(Notification.created_at.desc()).offset(offset).limit(limit)
    items = (await db.execute(query)).scalars().all()

    return PaginatedNotifications(
        items=items, total=total, limit=limit, offset=offset, unread_count=unread_count
    )


@router.patch("/{notification_id}/read", response_model=NotificationRead)
async def mark_read(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_active_user),
):
    notification = (
        await db.execute(
            select(Notification).where(
                Notification.id == notification_id, Notification.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if notification is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Not found")

    notification.is_read = True
    await db.commit()
    await db.refresh(notification)
    return notification