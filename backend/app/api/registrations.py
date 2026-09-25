import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request as HTTPRequest, status as http_status
from sqlalchemy import func as sqlfunc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import write_audit
from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import ApprovalStatus, Role, User
from app.schemas.user import PaginatedUsers, RegistrationDecision, UserRead
from app.users import require_role

router = APIRouter(prefix="/api/registrations", tags=["registrations"])
settings = get_settings()

# Staff know who lives where, so they approve, not only the admin.
reviewer = require_role(Role.staff, Role.admin)


@router.get("", response_model=PaginatedUsers)
async def list_registrations(
    status: Literal["pending", "rejected"] = Query("pending"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(reviewer),
):
    query = select(User).where(
        User.role == Role.citizen, User.approval_status == ApprovalStatus(status)
    )
    total = (
        await db.execute(select(sqlfunc.count()).select_from(query.subquery()))
    ).scalar_one()
    # Oldest first, so whoever signed up first gets checked first.
    query = query.order_by(User.created_at.asc()).offset(offset).limit(limit)
    items = (await db.execute(query)).scalars().all()
    return PaginatedUsers(items=items, total=total, limit=limit, offset=offset)


@router.patch("/{user_id}", response_model=UserRead)
async def decide_registration(
    user_id: uuid.UUID,
    payload: RegistrationDecision,
    http_request: HTTPRequest,
    db: AsyncSession = Depends(get_db),
    staff: User = Depends(reviewer),
):
    target = (
        await db.execute(select(User).where(User.id == user_id, User.role == Role.citizen))
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Not found")

    # Turning down an approved resident would let staff lock people out. That's
    # deactivation, and it's the admin's call on the Accounts screen.
    if target.approval_status == ApprovalStatus.approved:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT, detail="Already approved"
        )

    decision = ApprovalStatus(payload.approval_status)
    if (
        decision == ApprovalStatus.approved
        and settings.require_verified_email
        and not target.is_verified
    ):
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="Their email isn't confirmed yet",
        )
    if target.approval_status != decision:
        target.approval_status = decision
        ip = http_request.client.host if http_request.client else None
        await write_audit(
            db,
            actor_id=staff.id,
            action="user.approved" if decision == ApprovalStatus.approved else "user.rejected",
            object_type="user",
            object_id=str(target.id),
            detail=None,
            ip_address=ip,
        )
        await db.commit()
        await db.refresh(target)
    return target
