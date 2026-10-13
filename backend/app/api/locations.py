"""Puroks and streets for "Where is the problem?", and surges of reports.

Locations are optional: until the admin adds one, the submit form doesn't ask.
They are edited and switched off, never deleted, like categories.
"""

from fastapi import APIRouter, Depends, HTTPException, Request as HTTPRequest, status as http_status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import duplicates
from app.audit import write_audit
from app.db.session import get_db
from app.models.category import Category
from app.models.location import Location
from app.models.user import Role, User
from app.schemas.request import LocationCreate, LocationRead, LocationUpdate, Surge
from app.scoping import request_scope_filter
from app.users import current_active_user, require_role

router = APIRouter(tags=["locations"])


def _ip(http_request: HTTPRequest) -> str | None:
    return http_request.client.host if http_request.client else None


@router.get("/api/locations", response_model=list[LocationRead])
async def list_locations(db: AsyncSession = Depends(get_db), _: User = Depends(current_active_user)):
    query = select(Location).where(Location.is_active.is_(True)).order_by(Location.sort_order, Location.name)
    return (await db.execute(query)).scalars().all()


@router.get("/api/admin/locations", response_model=list[LocationRead])
async def list_all_locations(db: AsyncSession = Depends(get_db), _: User = Depends(require_role(Role.admin))):
    return (await db.execute(select(Location).order_by(Location.sort_order, Location.name))).scalars().all()


@router.post("/api/admin/locations", response_model=LocationRead, status_code=201)
async def create_location(
    payload: LocationCreate,
    http_request: HTTPRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_role(Role.admin)),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Name can't be empty")
    location = Location(name=name, sort_order=payload.sort_order)
    db.add(location)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(status_code=http_status.HTTP_409_CONFLICT, detail="That place is already listed")
    await write_audit(
        db,
        actor_id=admin.id,
        action="location.created",
        object_type="location",
        object_id=str(location.id),
        detail={"name": name},
        ip_address=_ip(http_request),
    )
    await db.commit()
    await db.refresh(location)
    return location


@router.patch("/api/admin/locations/{location_id}", response_model=LocationRead)
async def update_location(
    location_id: int,
    payload: LocationUpdate,
    http_request: HTTPRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_role(Role.admin)),
):
    location = await db.get(Location, location_id)
    if location is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Not found")
    changed = {}
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Name can't be empty")
        if getattr(location, field) != value:
            setattr(location, field, value)
            changed[field] = value
    if changed:
        try:
            await db.flush()
        except IntegrityError:
            raise HTTPException(status_code=http_status.HTTP_409_CONFLICT, detail="That place is already listed")
        await write_audit(
            db,
            actor_id=admin.id,
            action="location.updated",
            object_type="location",
            object_id=str(location.id),
            detail=changed,
            ip_address=_ip(http_request),
        )
        await db.commit()
        await db.refresh(location)
    return location


@router.get("/api/request-surges", response_model=list[Surge])
async def list_surges(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(Role.staff, Role.admin)),
):
    surges = []
    for row in await duplicates.surges(db, request_scope_filter(user)):
        category = await db.get(Category, row["category_id"])
        location = await db.get(Location, row["location_id"]) if row["location_id"] else None
        surges.append(Surge(category=category, location=location, count=row["count"], since=row["since"]))
    return surges
