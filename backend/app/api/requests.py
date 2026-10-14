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
from sqlalchemy import func as sqlfunc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import duplicates as dup
from app.audit import notify, write_audit
from app.classification import classify_and_route, handler_for
from app.db.session import get_db
from app.models.category import Category
from app.models.duplicate import DuplicateSuggestion
from app.models.location import Location
from app.models.enums import RequestStatus, Urgency
from app.models.request import Request
from app.models.status_history import StatusHistoryEntry
from app.models.user import Role, User
from app.queue_order import OPEN, aged_urgency_rank, flagged_first, mark_seen
from app.schemas.request import (
    DuplicateLink,
    DuplicateSuggestionRead,
    LinkReports,
    RequestRef,
    LinkReportsResult,
    SameProblemReport,
    SkippedReport,
    PaginatedRequests,
    RequestCreate,
    RequestRead,
    ReviewDecision,
    StatusUpdate,
    SuggestionDecision,
    UrgentFlag,
)
from app.scoping import request_scope_filter as _scope_filter
from app.users import current_active_user, require_role

router = APIRouter(prefix="/api/requests", tags=["requests"])

LEGAL_TRANSITIONS = dup.LEGAL_TRANSITIONS

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
        selectinload(Request.location),
        selectinload(Request.duplicate_of),
        selectinload(Request.linked_reports),
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
    http_request: HTTPRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(Role.citizen)),
):
    # Optional: a resident may report somewhere that isn't listed.
    if payload.location_id is not None:
        location = await db.get(Location, payload.location_id)
        if location is None or not location.is_active:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Pick a place from the list"
            )

    request = Request(
        reference_number=f"TEMP-{uuid.uuid4().hex[:8]}",
        citizen_id=user.id,
        description=payload.description,
        location_id=payload.location_id,
        status=RequestStatus.submitted,
    )
    db.add(request)
    await db.flush()

    year = datetime.now(timezone.utc).year
    request.reference_number = f"GAB-{year}-{request.id:05d}"

    # Who submitted what, and when, without the text itself.
    await write_audit(
        db,
        actor_id=user.id,
        action="request.submitted",
        object_type="request",
        object_id=str(request.id),
        detail=None,
        ip_address=http_request.client.host if http_request.client else None,
    )

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
    # Linked reports follow their main report, so staff work only the main one.
    # Residents still see their own.
    if user.role != Role.citizen:
        query = query.where(Request.duplicate_of_id.is_(None))
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
        # Requests a resident marked urgent first, then highest urgency, then
        # oldest, the order the queue is actually worked in. A request left
        # waiting sorts one level higher (app/queue_order.py). Unclassified
        # (null urgency) sorts last, and resolved requests, which only wait to
        # be closed, go below the rest.
        query = query.order_by(
            flagged_first(),
            (Request.status == RequestStatus.resolved).asc(),
            aged_urgency_rank().asc(),
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

    if request.duplicate_of_id is not None:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=f"This report follows {request.duplicate_of.reference_number}. Update that one",
        )

    to_status = RequestStatus(payload.to_status)
    if LEGAL_TRANSITIONS.get(request.status) != to_status:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=f"Cannot move from {request.status.value} to {to_status.value}",
        )

    from_status = request.status
    request.status = to_status
    mark_seen(request)
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

    # Linked reports move too. Each resident hears once, even with several reports.
    reports = await dup.follow_status(db, request, to_status, user.id, payload.note)
    message = STATUS_MESSAGES.get(to_status)
    if message:
        for report in reports:
            await notify(
                db,
                user_id=report.citizen_id,
                message=message,
                request_id=report.id,
                reference_number=report.reference_number,
            )

    await db.commit()
    return await _reload(db, request.id)


@router.put("/{request_id}/urgent-flag", response_model=RequestRead)
async def flag_urgent(
    request_id: int,
    payload: UrgentFlag,
    http_request: HTTPRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(Role.citizen)),
):
    # Only the resident who sent it. Anyone else gets the same 404 as for a
    # request that doesn't exist.
    request = (
        await db.execute(
            select(Request).where(Request.id == request_id, Request.citizen_id == user.id)
        )
    ).scalar_one_or_none()
    if request is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Not found")
    if request.status not in OPEN:
        raise HTTPException(status_code=http_status.HTTP_409_CONFLICT, detail="This request is already finished")
    if request.urgent_flagged_at is not None:
        raise HTTPException(status_code=http_status.HTTP_409_CONFLICT, detail="You already marked this as urgent")

    request.urgent_flagged_at = datetime.now(timezone.utc)
    request.urgent_reason = payload.reason
    # A linked report is off the queues, so the main report carries the pin.
    pinned = request
    if request.duplicate_of_id is not None:
        pinned = await db.get(Request, request.duplicate_of_id)
        if pinned.urgent_flagged_at is None:
            pinned.urgent_flagged_at = request.urgent_flagged_at
        # Pinned again, since this is news to staff.
        pinned.urgent_seen_at = None

    # The reason stays on the request only, not in the audit log.
    ip = http_request.client.host if http_request.client else None
    await write_audit(
        db,
        actor_id=user.id,
        action="request.flagged_urgent",
        object_type="request",
        object_id=str(request.id),
        detail=None,
        ip_address=ip,
    )
    if pinned.assigned_staff_id:
        await notify(
            db,
            user_id=pinned.assigned_staff_id,
            message="A resident marked this request as urgent",
            request_id=pinned.id,
            reference_number=pinned.reference_number,
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
    if request.duplicate_of_id is not None:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=f"This report follows {request.duplicate_of.reference_number}. Change that one",
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
    mark_seen(request)

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

    # Linked reports take the same labels, handler and status.
    await dup.follow_labels(db, request, user.id)
    # A new category can match other open reports.
    await dup.suggest_for(db, request)

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

async def _in_scope(db: AsyncSession, user: User, request_id: int, lock: bool = False) -> Request:
    query = select(Request).where(Request.id == request_id).options(*_load_options())
    if lock:
        query = query.with_for_update(of=Request)
    scope = _scope_filter(user)
    if scope is not None:
        query = query.where(scope)
    request = (await db.execute(query)).scalar_one_or_none()
    if request is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Not found")
    return request


@router.get("/{request_id}/duplicate-suggestions", response_model=list[DuplicateSuggestionRead])
async def list_duplicate_suggestions(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(Role.staff, Role.admin)),
):
    request = await _in_scope(db, user, request_id)
    if request.duplicate_of_id is not None:
        return []
    rows = (
        await db.execute(
            select(DuplicateSuggestion)
            .join(Request, Request.id == DuplicateSuggestion.candidate_id)
            .where(
                DuplicateSuggestion.request_id == request.id,
                DuplicateSuggestion.decision.is_(None),
                Request.status.in_(OPEN),
                Request.duplicate_of_id.is_(None),
                # Only reports the caller may see.
                *([scope] if (scope := _scope_filter(user)) is not None else []),
            )
            .order_by(DuplicateSuggestion.score.desc())
            .options(selectinload(DuplicateSuggestion.candidate))
        )
    ).scalars().all()
    # A report further along than the candidate can't be linked to it.
    return [s for s in rows if dup.rank(s.candidate.status) >= dup.rank(request.status)]


@router.get("/{request_id}/same-problem", response_model=list[SameProblemReport])
async def list_same_problem(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(Role.staff, Role.admin)),
):
    main = await _in_scope(db, user, request_id)
    return [
        SameProblemReport(
            id=r.id,
            reference_number=r.reference_number,
            description=r.description,
            status=r.status,
            created_at=r.created_at,
            score=round(score, 3),
            likely=likely,
        )
        for r, score, likely in await dup.same_problem(db, main, _scope_filter(user))
    ]


@router.post("/{request_id}/linked-reports", response_model=LinkReportsResult)
async def link_reports(
    request_id: int,
    payload: LinkReports,
    http_request: HTTPRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(Role.staff, Role.admin)),
):
    main = await _in_scope(db, user, request_id)
    ids = sorted(set(payload.request_ids) | {main.id})
    # Lock every row, lowest id first, so two staff linking at once can't deadlock.
    await db.execute(select(Request.id).where(Request.id.in_(ids)).order_by(Request.id).with_for_update())
    await db.refresh(main)
    query = select(Request).where(Request.id.in_(set(payload.request_ids)), Request.id != main.id)
    scope = _scope_filter(user)
    if scope is not None:
        query = query.where(scope)
    children = sorted((await db.execute(query)).scalars().all(), key=lambda r: r.created_at)
    ip = http_request.client.host if http_request.client else None
    linked, skipped = await dup.link_many(db, main, children, user.id, ip)
    # Asked for but not visible to this staff member, or gone.
    found = {r.id for r in children}
    missing = sorted(set(payload.request_ids) - found - {main.id})
    refs = dict(
        (await db.execute(select(Request.id, Request.reference_number).where(Request.id.in_(missing)))).all()
    ) if missing else {}

    not_same_ids = set(payload.not_same) - set(payload.request_ids) - {main.id}
    if not_same_ids:
        others = select(Request).where(Request.id.in_(not_same_ids))
        if scope is not None:
            others = others.where(scope)
        await dup.mark_not_same(db, main, list((await db.execute(others)).scalars().all()), user.id, ip)

    await db.commit()
    return LinkReportsResult(
        linked=[RequestRef(id=r.id, reference_number=r.reference_number) for r in linked],
        skipped=[SkippedReport(id=r.id, reference_number=r.reference_number, reason=reason) for r, reason in skipped]
        + [SkippedReport(id=i, reference_number=refs.get(i, f"#{i}"), reason="Not found") for i in missing],
    )


@router.patch("/{request_id}/duplicate-suggestions/{suggestion_id}", status_code=204)
async def dismiss_duplicate_suggestion(
    request_id: int,
    suggestion_id: int,
    payload: SuggestionDecision,
    http_request: HTTPRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(Role.staff, Role.admin)),
):
    await _in_scope(db, user, request_id)
    suggestion = await db.get(DuplicateSuggestion, suggestion_id)
    if suggestion is None or suggestion.request_id != request_id:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Not found")
    if suggestion.decision is None:
        suggestion.decision = payload.decision
        suggestion.decided_by = user.id
        suggestion.decided_at = datetime.now(timezone.utc)
        await write_audit(
            db,
            actor_id=user.id,
            action="request.duplicate_dismissed",
            object_type="request",
            object_id=str(request_id),
            detail={"candidate": suggestion.candidate_id},
            ip_address=http_request.client.host if http_request.client else None,
        )
        await db.commit()


@router.put("/{request_id}/duplicate-of", response_model=RequestRead)
async def link_duplicate(
    request_id: int,
    payload: DuplicateLink,
    http_request: HTTPRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(Role.staff, Role.admin)),
):
    child = await _in_scope(db, user, request_id)
    main_query = select(Request).where(Request.reference_number == payload.reference_number.strip().upper())
    scope = _scope_filter(user)
    if scope is not None:
        main_query = main_query.where(scope)
    main = (await db.execute(main_query)).scalar_one_or_none()
    if main is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="No report with that number")
    # Lock both rows, lower id first, so two staff linking opposite ways can't deadlock.
    await db.execute(
        select(Request.id).where(Request.id.in_([child.id, main.id])).order_by(Request.id).with_for_update()
    )
    await db.refresh(child)
    await db.refresh(main)
    await dup.link(db, child, main, user.id, http_request.client.host if http_request.client else None)
    await db.commit()
    return await _reload(db, child.id)


@router.delete("/{request_id}/duplicate-of", response_model=RequestRead)
async def unlink_duplicate(
    request_id: int,
    http_request: HTTPRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(Role.staff, Role.admin)),
):
    child = await _in_scope(db, user, request_id, lock=True)
    await dup.unlink(db, child, user.id, http_request.client.host if http_request.client else None)
    await db.commit()
    return await _reload(db, child.id)
