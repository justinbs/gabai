import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request as HTTPRequest, Response, status as http_status
from fastapi_users.exceptions import InvalidPasswordException
from sqlalchemy import func as sqlfunc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import passwords
from app.audit import write_audit
from app.db.session import get_db
from app.models.user import ApprovalStatus, Role, User
from app.schemas.user import AdminUserCreate, AdminUserUpdate, PaginatedUsers, TemporaryPassword, UserRead
from app.users import UserManager, get_user_manager, require_role

router = APIRouter(prefix="/api/admin/users", tags=["admin"])


@router.get("", response_model=PaginatedUsers)
async def list_users(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    role: Role | None = Query(None),
    is_active: bool | None = Query(None),
    q: str | None = Query(None, max_length=200),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_role(Role.admin)),
):
    query = select(User)
    if role:
        query = query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    if q:
        like = f"%{q}%"
        query = query.where(or_(User.email.ilike(like), User.full_name.ilike(like)))

    total = (
        await db.execute(select(sqlfunc.count()).select_from(query.subquery()))
    ).scalar_one()

    query = query.order_by(User.created_at.desc()).offset(offset).limit(limit)
    items = (await db.execute(query)).scalars().all()

    return PaginatedUsers(items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=UserRead, status_code=201)
async def create_user(
    payload: AdminUserCreate,
    http_request: HTTPRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_role(Role.admin)),
    user_manager: UserManager = Depends(get_user_manager),
):
    email = payload.email.lower()
    existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=http_status.HTTP_409_CONFLICT, detail="Email already in use")

    # This path hashes directly instead of going through the manager, so the
    # policy has to be called here too or it binds residents and not staff.
    try:
        await user_manager.validate_password(payload.password, payload)
    except InvalidPasswordException as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.reason
        )

    user = User(
        email=email,
        hashed_password=user_manager.password_helper.hash(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        is_active=True,
        is_verified=False,
        is_superuser=False,
        # The admin chose this password and knows it.
        must_change_password=True,
        # An admin made it, so there's no one to confirm.
        approval_status=ApprovalStatus.approved,
    )
    db.add(user)
    await db.flush()

    ip = http_request.client.host if http_request.client else None
    await write_audit(
        db,
        actor_id=admin.id,
        action="user.created",
        object_type="user",
        object_id=str(user.id),
        detail={"role": user.role.value},
        ip_address=ip,
    )

    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: uuid.UUID,
    payload: AdminUserUpdate,
    http_request: HTTPRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_role(Role.admin)),
):
    target = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Not found")

    would_strand_admins = False
    if target.role == Role.admin and target.is_active:
        active_admin_count = (
            await db.execute(
                select(sqlfunc.count())
                .select_from(User)
                .where(User.role == Role.admin, User.is_active.is_(True))
            )
        ).scalar_one()
        if active_admin_count == 1:
            demoting = payload.role is not None and payload.role != Role.admin
            deactivating = payload.is_active is False
            would_strand_admins = demoting or deactivating

    if would_strand_admins:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="Cannot remove the last active admin",
        )

    previous_role = target.role
    previous_active = target.is_active

    if payload.full_name is not None:
        target.full_name = payload.full_name
    if payload.role is not None:
        target.role = payload.role
    if payload.is_active is not None:
        target.is_active = payload.is_active

    ip = http_request.client.host if http_request.client else None

    if payload.role is not None and payload.role != previous_role:
        await write_audit(
            db,
            actor_id=admin.id,
            action="user.role_changed",
            object_type="user",
            object_id=str(target.id),
            detail={"from": previous_role.value, "to": payload.role.value},
            ip_address=ip,
        )

    if payload.is_active is False and previous_active:
        await write_audit(
            db,
            actor_id=admin.id,
            action="user.deactivated",
            object_type="user",
            object_id=str(target.id),
            detail=None,
            ip_address=ip,
        )

    await db.commit()
    await db.refresh(target)
    return target


@router.post("/{user_id}/password", response_model=TemporaryPassword)
async def reset_password(
    user_id: uuid.UUID,
    http_request: HTTPRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_role(Role.admin)),
    user_manager: UserManager = Depends(get_user_manager),
):
    target = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Not found")

    temporary = passwords.generate_temporary()
    target.hashed_password = user_manager.password_helper.hash(temporary)
    target.must_change_password = True

    # No detail. The audit log is readable by every admin, and the plaintext
    # must exist only in this response.
    ip = http_request.client.host if http_request.client else None
    await write_audit(
        db,
        actor_id=admin.id,
        action="user.password_reset",
        object_type="user",
        object_id=str(target.id),
        detail=None,
        ip_address=ip,
    )
    await db.commit()

    response.headers["Cache-Control"] = "no-store"
    return TemporaryPassword(temporary_password=temporary)
