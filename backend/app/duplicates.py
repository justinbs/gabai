"""Duplicate reports: suggesting them, linking them, and spotting surges.

When many residents report one problem, staff link the others to one main
report, all at once from that report's page or from the surge notice. Linked reports leave the queues, take the main
report's labels and handler, and follow its status, so one action reaches
everyone who reported it.

Suggestions only: staff confirm every link, and a wrong one can be undone at
any time. Word overlap compares two reports with each other; it never
touches urgency or the model.
"""

import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status as http_status
from sqlalchemy import func, or_, select
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


async def link(
    db: AsyncSession, child: Request, main: Request, actor_id: uuid.UUID, ip: str | None, tell_resident: bool = True
) -> None:
    """Link child to main, then bring child up to main's labels, handler and status."""
    if child.id == main.id:
        raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A report can't be linked to itself")
    if main.status == RequestStatus.submitted:
        raise _conflict(f"{main.reference_number} isn't sorted yet. Label it in For review first")
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
    # The classifier leaves alone anything no longer at submitted.
    if child.status == RequestStatus.submitted:
        _move(db, child, RequestStatus.under_review, actor_id, note)
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
    if tell_resident:
        await _tell_linked(db, child, main)


async def _tell_linked(db: AsyncSession, child: Request, main: Request) -> None:
    await notify(
        db,
        user_id=child.citizen_id,
        message="Others reported the same problem. You'll get the same updates",
        request_id=child.id,
        reference_number=child.reference_number,
    )


async def link_many(
    db: AsyncSession, main: Request, children: list[Request], actor_id: uuid.UUID, ip: str | None
) -> tuple[list[Request], list[tuple[Request, str]]]:
    """Link each report to main. One that can't be linked is skipped with the reason."""
    linked, skipped, told = [], [], set()
    for child in children:
        try:
            await link(db, child, main, actor_id, ip, tell_resident=False)
        except HTTPException as exc:
            skipped.append((child, exc.detail))
            continue
        linked.append(child)
        # One notice per resident, however many of their reports were linked.
        if child.citizen_id not in told:
            told.add(child.citizen_id)
            await _tell_linked(db, child, main)
    return linked, skipped


async def mark_not_same(
    db: AsyncSession, main: Request, others: list[Request], actor_id: uuid.UUID, ip: str | None
) -> None:
    """Staff unticked these, so they aren't listed against main again."""
    for other in others:
        await db.execute(
            insert(DuplicateSuggestion)
            .values(
                request_id=other.id,
                candidate_id=main.id,
                score=round(overlap(main.description, other.description), 3),
                decision="dismissed",
                decided_by=actor_id,
                decided_at=func.now(),
            )
            .on_conflict_do_update(
                constraint="uq_duplicate_suggestion_pair",
                set_={"decision": "dismissed", "decided_by": actor_id, "decided_at": func.now()},
            )
        )
        await write_audit(
            db,
            actor_id=actor_id,
            action="request.duplicate_dismissed",
            object_type="request",
            object_id=str(other.id),
            detail={"candidate": main.id},
            ip_address=ip,
        )


async def same_problem(db: AsyncSession, main: Request, scope) -> list[tuple[Request, float, bool]]:
    """Open reports that could be linked to main, most alike first.

    Within the window either side of main. Listed when the words mostly match,
    whatever category the model gave it, since one flood can be sorted several
    ways. Also listed, unticked: the same category, or the same place within
    the hour. A place on both reports has to match. Reports staff marked as
    not the same are left out.

    Returns (report, word overlap, ticked at the start).
    """
    category_id = effective_category_id(main)
    if category_id is None or main.duplicate_of_id is not None or main.status not in OPEN:
        return []
    query = select(Request).where(
        Request.id != main.id,
        Request.status.in_(OPEN),
        Request.duplicate_of_id.is_(None),
        Request.created_at >= main.created_at - WINDOW,
        Request.created_at <= main.created_at + WINDOW,
    )
    if main.location_id is not None:
        query = query.where((Request.location_id.is_(None)) | (Request.location_id == main.location_id))
    if scope is not None:
        query = query.where(scope)
    dismissed = set(
        (
            await db.execute(
                select(DuplicateSuggestion.request_id, DuplicateSuggestion.candidate_id).where(
                    DuplicateSuggestion.decision == "dismissed",
                    or_(DuplicateSuggestion.request_id == main.id, DuplicateSuggestion.candidate_id == main.id),
                )
            )
        ).all()
    )
    parents = set(
        (
            await db.execute(select(Request.duplicate_of_id).where(Request.duplicate_of_id.is_not(None)).distinct())
        ).scalars().all()
    )
    found = []
    for other in (await db.execute(query)).scalars().all():
        if other.id in parents or rank(other.status) > rank(main.status):
            continue
        if (other.id, main.id) in dismissed or (main.id, other.id) in dismissed:
            continue
        score = overlap(main.description, other.description)
        same_category = effective_category_id(other) == category_id
        same_place = (
            main.location_id is not None
            and other.location_id == main.location_id
            and abs(other.created_at - main.created_at) <= SURGE_WINDOW
        )
        likely = score >= MIN_OVERLAP
        if likely or same_category or same_place:
            found.append((other, score, likely))
    found.sort(key=lambda row: (not row[2], -row[1], row[0].created_at))
    return found


async def unlink(db: AsyncSession, child: Request, actor_id: uuid.UUID, ip: str | None) -> None:
    """Undo a link. A report the link marked finished goes back to For review."""
    if child.duplicate_of_id is None:
        raise _conflict("This report isn't linked")
    main = await db.get(Request, child.duplicate_of_id)
    child.duplicate_of_id = None
    if child.status in (RequestStatus.resolved, RequestStatus.closed):
        _move(db, child, RequestStatus.under_review, actor_id, "Linked by mistake, checking it again")
        child.resolved_at = None
        child.assigned_staff_id = None
        await notify(
            db,
            user_id=child.citizen_id,
            message="Your request is being checked again",
            request_id=child.id,
            reference_number=child.reference_number,
        )
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


async def follow_status(
    db: AsyncSession, main: Request, to_status: RequestStatus, actor_id, note: str | None = None
) -> list[Request]:
    """Move linked reports with the main one.

    Returns one report per resident to notify, their own, so a resident with
    several linked reports hears once.
    """
    per_citizen = {main.citizen_id: main}
    for child in await linked_to(db, main):
        if LEGAL_TRANSITIONS.get(child.status) == to_status:
            _move(db, child, to_status, actor_id, note or f"Follows {main.reference_number}")
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
    found = []
    for row in (await db.execute(query)).all():
        surge = dict(row._mapping)
        members = select(Request).where(
            Request.created_at >= since,
            Request.duplicate_of_id.is_(None),
            category == surge["category_id"],
            Request.status.in_(OPEN),
            Request.status != RequestStatus.submitted,
            Request.location_id.is_(None) if surge["location_id"] is None else Request.location_id == surge["location_id"],
        )
        if scope is not None:
            members = members.where(scope)
        candidates = (await db.execute(members)).scalars().all()
        # The report to link the rest to: the one furthest along, then the oldest.
        surge["main"] = min(candidates, key=lambda r: (-rank(r.status), r.created_at)) if candidates else None
        found.append(surge)
    return found
