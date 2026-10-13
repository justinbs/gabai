"""Duplicate reports: suggesting them, linking them, and spotting surges.

When many residents report one problem, staff link the newer reports to the
oldest one, the main report. Linked reports leave the queues, take the main
report's labels and handler, and follow its status, so one action reaches
everyone who reported it.

Suggestions only: staff confirm every link, so a different problem is never
hidden by mistake. Word overlap compares two reports with each other; it never
touches urgency or the model.
"""

import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status as http_status
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import notify, write_audit
from app.models.duplicate import DuplicateSuggestion
from app.models.enums import RequestStatus
from app.models.request import Request
from app.models.status_history import StatusHistoryEntry
from app.queue_order import OPEN

# Only reports this recent are compared.
WINDOW = timedelta(hours=72)
# Share of distinct words two reports have in common. Low on purpose: residents
# describe one problem in different words, and staff confirm every link.
MIN_OVERLAP = 0.3
# A surge is this many reports in one category and place within the hour.
SURGE_COUNT = 5
SURGE_WINDOW = timedelta(hours=1)

LEGAL_TRANSITIONS: dict[RequestStatus, RequestStatus] = {
    RequestStatus.routed: RequestStatus.in_progress,
    RequestStatus.in_progress: RequestStatus.resolved,
    RequestStatus.resolved: RequestStatus.closed,
}
# How far along a report is. Everything before routing counts as 0.
RANK = {RequestStatus.routed: 1, RequestStatus.in_progress: 2, RequestStatus.resolved: 3, RequestStatus.closed: 4}


def rank(status: RequestStatus) -> int:
    return RANK.get(status, 0)


def words(text: str) -> set[str]:
    # Same split as the paper's near-duplicate check (ml/scripts/evaluate_deployed.py).
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def overlap(a: str, b: str) -> float:
    wa, wb = words(a), words(b)
    return len(wa & wb) / len(wa | wb) if wa and wb else 0.0


def effective_category_id(request: Request) -> int | None:
    return request.final_category_id or request.predicted_category_id


async def suggest_for(db: AsyncSession, request: Request) -> None:
    """Store suggestions pointing this report at older open ones like it."""
    category_id = effective_category_id(request)
    if category_id is None or request.duplicate_of_id is not None:
        return
    has_links = (
        await db.execute(select(func.count()).select_from(Request).where(Request.duplicate_of_id == request.id))
    ).scalar_one()
    if has_links:
        return

    query = select(Request).where(
        Request.id != request.id,
        Request.status.in_(OPEN),
        Request.duplicate_of_id.is_(None),
        Request.created_at >= request.created_at - WINDOW,
        Request.created_at <= request.created_at,
        func.coalesce(Request.final_category_id, Request.predicted_category_id) == category_id,
    )
    # A place on both reports has to match; a report with no place can match any.
    if request.location_id is not None:
        query = query.where(
            (Request.location_id.is_(None)) | (Request.location_id == request.location_id)
        )
    for candidate in (await db.execute(query)).scalars().all():
        score = overlap(request.description, candidate.description)
        if score >= MIN_OVERLAP:
            await db.execute(
                insert(DuplicateSuggestion)
                .values(request_id=request.id, candidate_id=candidate.id, score=round(score, 3))
                .on_conflict_do_nothing(constraint="uq_duplicate_suggestion_pair")
            )


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=http_status.HTTP_409_CONFLICT, detail=detail)


def _move(db: AsyncSession, request: Request, to_status: RequestStatus, actor_id, note: str) -> None:
    db.add(
        StatusHistoryEntry(
            request_id=request.id,
            from_status=request.status,
            to_status=to_status,
            actor_id=actor_id,
            note=note,
        )
    )
    request.status = to_status
    if to_status in (RequestStatus.resolved, RequestStatus.closed) and request.resolved_at is None:
        request.resolved_at = datetime.now(timezone.utc)


async def link(db: AsyncSession, child: Request, main: Request, actor_id: uuid.UUID, ip: str | None) -> None:
    """Link child to main, then bring child up to main's labels, handler and status."""
    if child.id == main.id:
        raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A report can't be linked to itself")
    # The classifier would overwrite a link made while it's still working.
    if RequestStatus.submitted in (child.status, main.status):
        raise _conflict("Still being sorted, try again in a minute")
    if child.duplicate_of_id is not None:
        raise _conflict("This report is already linked")
    if main.duplicate_of_id is not None:
        raise _conflict(f"{main.reference_number} is itself linked to another report. Link to that one instead")
    children = (
        await db.execute(select(func.count()).select_from(Request).where(Request.duplicate_of_id == child.id))
    ).scalar_one()
    if children:
        raise _conflict("Other reports are linked to this one, so it can't be linked")
    if main.status == RequestStatus.closed:
        raise _conflict(f"{main.reference_number} is closed")
    if child.status in (RequestStatus.resolved, RequestStatus.closed):
        raise _conflict("This report is already finished")
    if rank(child.status) > rank(main.status):
        raise _conflict(f"This report is further along than {main.reference_number}. Link that one to this report instead")

    note = f"Linked to {main.reference_number}"
    child.duplicate_of_id = main.id
    child.final_category_id = effective_category_id(main)
    child.final_urgency = main.final_urgency or main.predicted_urgency
    child.assigned_staff_id = main.assigned_staff_id

    # Walk the allowed steps, one history row each, so the timeline stays true.
    if rank(main.status) >= 1 and rank(child.status) == 0:
        _move(db, child, RequestStatus.routed, actor_id, note)
    while rank(child.status) < rank(main.status):
        _move(db, child, LEGAL_TRANSITIONS[child.status], actor_id, note)

    await db.execute(
        DuplicateSuggestion.__table__.update()
        .where(DuplicateSuggestion.request_id == child.id, DuplicateSuggestion.candidate_id == main.id)
        .values(decision="linked", decided_by=actor_id, decided_at=func.now())
    )
    await write_audit(
        db,
        actor_id=actor_id,
        action="request.linked",
        object_type="request",
        object_id=str(child.id),
        detail={"to": main.id},
        ip_address=ip,
    )
    await notify(
        db,
        user_id=child.citizen_id,
        message=f"Others reported the same problem. Your report now follows {main.reference_number}",
        request_id=child.id,
        reference_number=child.reference_number,
    )


async def unlink(db: AsyncSession, child: Request, actor_id: uuid.UUID, ip: str | None) -> None:
    """Undo a link while the main report is open. The report keeps its labels and status."""
    if child.duplicate_of_id is None:
        raise _conflict("This report isn't linked")
    main = await db.get(Request, child.duplicate_of_id)
    if main is not None and main.status not in OPEN:
        raise _conflict(f"{main.reference_number} is finished, so the link stays")
    child.duplicate_of_id = None
    await write_audit(
        db,
        actor_id=actor_id,
        action="request.unlinked",
        object_type="request",
        object_id=str(child.id),
        detail={"from": main.id if main else None},
        ip_address=ip,
    )


async def linked_to(db: AsyncSession, main: Request) -> list[Request]:
    return list(
        (await db.execute(select(Request).where(Request.duplicate_of_id == main.id).with_for_update())).scalars().all()
    )


async def follow_status(db: AsyncSession, main: Request, to_status: RequestStatus, actor_id) -> list[Request]:
    """Move linked reports with the main one.

    Returns one report per resident to notify, their own, so a resident with
    several linked reports hears once.
    """
    per_citizen = {main.citizen_id: main}
    for child in await linked_to(db, main):
        if LEGAL_TRANSITIONS.get(child.status) == to_status:
            _move(db, child, to_status, actor_id, f"Follows {main.reference_number}")
            per_citizen.setdefault(child.citizen_id, child)
    return list(per_citizen.values())


async def follow_labels(db: AsyncSession, main: Request, actor_id) -> set[uuid.UUID]:
    """After main is relabelled, linked reports take the same labels, handler and status."""
    moved = set()
    for child in await linked_to(db, main):
        child.final_category_id = main.final_category_id
        child.final_urgency = main.final_urgency
        child.assigned_staff_id = main.assigned_staff_id
        if child.status != main.status:
            _move(db, child, main.status, actor_id, f"Follows {main.reference_number}")
            moved.add(child.citizen_id)
    return moved


async def surges(db: AsyncSession, scope) -> list[dict]:
    """Five or more unlinked reports in one category and place within the hour."""
    since = datetime.now(timezone.utc) - SURGE_WINDOW
    category = func.coalesce(Request.final_category_id, Request.predicted_category_id)
    query = (
        select(category.label("category_id"), Request.location_id, func.count().label("count"), func.min(Request.created_at).label("since"))
        .where(Request.created_at >= since, Request.duplicate_of_id.is_(None), category.is_not(None))
        .group_by(category, Request.location_id)
        .having(func.count() >= SURGE_COUNT)
    )
    if scope is not None:
        query = query.where(scope)
    return [dict(row._mapping) for row in (await db.execute(query)).all()]
