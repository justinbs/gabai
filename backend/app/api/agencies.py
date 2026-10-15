"""Agencies a concern can be referred to. Edited and switched off, never deleted."""

from fastapi import APIRouter, Depends, HTTPException, Request as HTTPRequest, status as http_status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import write_audit
from app.db.session import get_db
from app.models.referral_agency import ReferralAgency
from app.models.user import Role, User
from app.schemas.request import AgencyCreate, AgencyRead, AgencyUpdate
from app.users import require_role

router = APIRouter(tags=["agencies"])


def _ip(r: HTTPRequest) -> str | None:
    return r.client.host if r.client else None


@router.get("/api/agencies", response_model=list[AgencyRead])
async def list_agencies(db: AsyncSession = Depends(get_db), _: User = Depends(require_role(Role.staff, Role.admin))):
    q = select(ReferralAgency).where(ReferralAgency.is_active.is_(True)).order_by(ReferralAgency.sort_order, ReferralAgency.name)
    return (await db.execute(q)).scalars().all()


@router.get("/api/admin/agencies", response_model=list[AgencyRead])
async def list_all_agencies(db: AsyncSession = Depends(get_db), _: User = Depends(require_role(Role.admin))):
    q = select(ReferralAgency).order_by(ReferralAgency.sort_order, ReferralAgency.name)
    return (await db.execute(q)).scalars().all()


@router.post("/api/admin/agencies", response_model=AgencyRead, status_code=201)
async def create_agency(
    payload: AgencyCreate,
    http_request: HTTPRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_role(Role.admin)),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Name can't be empty")
    agency = ReferralAgency(name=name, sort_order=payload.sort_order)
    db.add(agency)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(status_code=http_status.HTTP_409_CONFLICT, detail="That agency is already listed")
    await write_audit(db, actor_id=admin.id, action="agency.created", object_type="agency",
                      object_id=str(agency.id), detail={"name": name}, ip_address=_ip(http_request))
    await db.commit()
    await db.refresh(agency)
    return agency


@router.patch("/api/admin/agencies/{agency_id}", response_model=AgencyRead)
async def update_agency(
    agency_id: int,
    payload: AgencyUpdate,
    http_request: HTTPRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_role(Role.admin)),
):
    agency = await db.get(ReferralAgency, agency_id)
    if agency is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Not found")
    changed = {}
    for field, value in payload.model_dump(exclude_unset=True).items():
        # A contact field sent as null is cleared. These three can't be.
        if field in ("name", "is_active", "sort_order") and value is None:
            continue
        if isinstance(value, str):
            value = value.strip() or None
        if field == "name" and not value:
            raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Name can't be empty")
        if getattr(agency, field) != value:
            setattr(agency, field, value)
            changed[field] = value
    if changed:
        try:
            await db.flush()
        except IntegrityError:
            raise HTTPException(status_code=http_status.HTTP_409_CONFLICT, detail="That agency is already listed")
        await write_audit(db, actor_id=admin.id, action="agency.updated", object_type="agency",
                          object_id=str(agency.id), detail=changed, ip_address=_ip(http_request))
        await db.commit()
        await db.refresh(agency)
    return agency