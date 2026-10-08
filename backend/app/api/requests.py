import uuid
from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request as HTTPRequest,
    status as http_status,
)
from sqlalchemy import case, func as sqlfunc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.audit import notify, write_audit
from app.classification import classify_and_route, handler_for
from app.db.session import get_db
from app.models.category import Category
from app.models.enums import RequestStatus, Urgency
from app.models.request import Request
from app.models.status_history import StatusHistoryEntry
from app.models.user import Role, User
from app.schemas.request import (
    PaginatedRequests,
    RequestCreate,
    RequestRead,
    ReviewDecision,
    StatusUpdate,
)
from app.scoping import request_scope_filter as _scope_filter
from app.users import current_active_user, require_role

router = APIRouter(prefix="/api/requests", tags=["requests"])

LEGAL_TRANSITIONS: dict[RequestStatus, RequestStatus] = {
    RequestStatus.routed: RequestStatus.in_progress,
    RequestStatus.in_progress: RequestStatus.resolved,
    RequestStatus.resolved: RequestStatus.closed,
}

STATUS_MESSAGES: dict[RequestStatus, str] = {
    RequestStatus.in_progress: "Your request is being worked on",
    RequestStatus.resolved: "Your request is done",
    RequestStatus.closed: "Your request is closed",
}


def _load_options():
    return (
        selectinload(Request.citizen),
        selectinload(Request.predicted_category),
        selectinload(Request.final_category),
        selectinload(Request.assigned_staff),
        selectinload(Request.attachments),
        selectinload(Request.status_history).selectinload(StatusHistoryEntry.actor),
    )


async def _reload(db: AsyncSession, request_id: int) -> Request:
    db.expire_all()
    result = await db.execute(
        select(Request).where(Request.id == request_id).options(*_load_options())
    )
    return result.scalar_one()


@router.post("", response_model=RequestRead, status_code=201)
async def submit_request(
    payload: RequestCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(Role.citizen)),
):
    request = Request(
        reference_number=f"TEMP-{uuid.uuid4().hex[:8]}",
        citizen_id=user.id,
        description=payload.description,
        status=RequestStatus.submitted,
    )
    db.add(request)
    await db.flush()

    year = datetime.now(timezone.utc).year
    request.reference_number = f"GAB-{year}-{request.id:05d}"

    db.add(
        StatusHistoryEntry(
            request_id=request.id,
            from_status=None,
            to_status=RequestStatus.submitted,
            actor_id=user.id,
            note=None,
        )
    )

    await db.commit()

    # After the response, so the resident gets a reference number without
    # waiting on inference.
    background_tasks.add_task(classify_and_route, request.id)
    return await _reload(db, request.id)


@router.get("", response_model=PaginatedRequests)
async def list_requests(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status_filter: list[RequestStatus] | None = Query(None, alias="status"),
    category_id: int | None = Query(None),
    urgency_filter: Urgency | None = Query(None, alias="urgency"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_active_user),
):
    effective_category_id = sqlfunc.coalesce(Request.final_category_id, Request.predicted_category_id)
    effective_urgency = sqlfunc.coalesce(Request.final_urgency, Request.predicted_urgency)

    query = select(Request)

    scope = _scope_filter(user)
    if scope is not None:
        query = query.where(scope)
    if status_filter:
        query = query.where(Request.status.in_(status_filter))
    if category_id:
        query = query.where(effective_category_id == category_id)
    if urgency_filter:
        query = query.where(effective_urgency == urgency_filter)

    total = (
        await db.execute(select(sqlfunc.count()).select_from(query.subquery()))
    ).scalar_one()

    if user.role == Role.citizen:
        query = query.order_by(Request.created_at.desc())
    else:
        # Highest urgency first, then oldest first — the order the queue is
        # actually worked in. Unclassified (null urgency) sorts last, and
        # resolved requests, which only wait to be closed, go below the rest.
        urgency_rank = case(
            (effective_urgency == Urgency.high, 0),
            (effective_urgency == Urgency.medium, 1),
            (effective_urgency == Urgency.low, 2),
            else_=3,
        )
        query = query.order_by(
            (Request.status == RequestStatus.resolved).asc(),
            urgency_rank.asc(),
            Request.created_at.asc(),
        )

    query = query.offset(offset).limit(limit).options(*_load_options())
    items = (await db.execute(query)).scalars().all()

    return PaginatedRequests(items=items, total=total, limit=limit, offset=offset)


@router.get("/{request_id}", response_model=RequestRead)
async def get_request(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_active_user),
):
    query = select(Request).where(Request.id == request_id).options(*_load_options())
    scope = _scope_filter(user)
    if scope is not None:
        query = query.where(scope)

    request = (await db.execute(query)).scalar_one_or_none()
    if request is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Not found")
    return request


@router.patch("/{request_id}/status", response_model=RequestRead)
async def update_status(
    request_id: int,
    payload: StatusUpdate,
    http_request: HTTPRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(Role.staff, Role.admin)),
):
    query = select(Request).where(Request.id == request_id).options(*_load_options())
    scope = _scope_filter(user)
    if scope is not None:
        query = query.where(scope)

    request = (await db.execute(query)).scalar_one_or_none()
    if request is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Not found")

    to_status = RequestStatus(payload.to_status)
    if LEGAL_TRANSITIONS.get(request.status) != to_status:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=f"Cannot move from {request.status.value} to {to_status.value}",
        )

    from_status = request.status
    request.status = to_status
    if to_status in (RequestStatus.resolved, RequestStatus.closed) and request.resolved_at is None:
        request.resolved_at = datetime.now(timezone.utc)

    db.add(
        StatusHistoryEntry(
            request_id=request.id,
            from_status=from_status,
            to_status=to_status,
            actor_id=user.id,
            note=payload.note,
        )
    )

    ip = http_request.client.host if http_request.client else None
    await write_audit(
        db,
        actor_id=user.id,
        action="request.status_changed",
        object_type="request",
        object_id=str(request.id),
        detail={"from": from_status.value, "to": to_status.value},
        ip_address=ip,
    )

    message = STATUS_MESSAGES.get(to_status)
    if message:
        await notify(
            db,
            user_id=request.citizen_id,
            message=message,
            request_id=request.id,
            reference_number=request.reference_number,
        )

    await db.commit()
    return await _reload(db, request.id)


@router.patch("/{request_id}/classification", response_model=RequestRead)
async def set_classification(
    request_id: int,
    payload: ReviewDecision,
    http_request: HTTPRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(Role.staff, Role.admin)),
):
    # Locked so a late classification cannot overwrite this label.
    query = (
        select(Request)
        .where(Request.id == request_id)
        .options(*_load_options())
        .with_for_update(of=Request)
    )
    scope = _scope_filter(user)
    if scope is not None:
        query = query.where(scope)

    request = (await db.execute(query)).scalar_one_or_none()
    if request is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Not found")

    if request.status in (RequestStatus.resolved, RequestStatus.closed):
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="Request is finished and cannot be relabelled.",
        )

    # The category must exist and be switched on.
    category = await db.get(Category, payload.final_category_id)
    if category is None or not category.is_active:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Pick a category that is switched on",
        )

    from_status = request.status
    previous_assigned_staff_id = request.assigned_staff_id

    request.final_category_id = payload.final_category_id
    request.final_urgency = payload.final_urgency

    handler_id = await handler_for(db, payload.final_category_id)
    # Only claim routed when somebody actually owns it. Writing routed with no
    # assignee puts a request outside every staff member's scope, which is how
    # it would vanish for everyone but an admin.
    if handler_id is not None:
        request.assigned_staff_id = handler_id
        request.status = RequestStatus.routed
    else:
        request.status = RequestStatus.under_review

    db.add(
        StatusHistoryEntry(
            request_id=request.id,
            from_status=from_status,
            to_status=request.status,
            actor_id=user.id,
            note=payload.note,
        )
    )

    ip = http_request.client.host if http_request.client else None
    await write_audit(
        db,
        actor_id=user.id,
        action="request.reclassified",
        object_type="request",
        object_id=str(request.id),
        detail={"category_id": payload.final_category_id, "urgency": payload.final_urgency.value},
        ip_address=ip,
    )

    moved = handler_id is not None and handler_id != previous_assigned_staff_id
    if moved:
        message = (
            "Your request went to another office"
            if previous_assigned_staff_id is not None
            else "A staff member is now handling your request"
        )
        await notify(
            db,
            user_id=request.citizen_id,
            message=message,
            request_id=request.id,
            reference_number=request.reference_number,
        )

    await db.commit()
    return await _reload(db, request.id)