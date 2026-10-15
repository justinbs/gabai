"""Queue order for staff: flagged first, then urgency raised by waiting time.

Waiting only changes the order, never the stored urgency. A request nobody has
moved for a while sorts one level higher, so a concern rated too low still
reaches the top eventually.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, select

from app.models.enums import RequestStatus, Urgency
from app.models.request import Request
from app.models.status_history import StatusHistoryEntry

# How long untouched before a request sorts one level up.
AGE_LOW = timedelta(hours=48)
AGE_MEDIUM = timedelta(hours=24)

# Waiting for someone to act. In progress means someone already is.
WAITING = (RequestStatus.submitted, RequestStatus.under_review, RequestStatus.routed)
OPEN = (RequestStatus.submitted, RequestStatus.under_review, RequestStatus.routed, RequestStatus.in_progress)


def _last_touched():
    latest = (
        select(func.max(StatusHistoryEntry.created_at))
        .where(StatusHistoryEntry.request_id == Request.id)
        .correlate(Request)
        .scalar_subquery()
    )
    return func.coalesce(latest, Request.created_at)


def flagged_first():
    # A resident's urgent flag counts until staff first act on the request.
    return case(
        (
            (Request.urgent_flagged_at.is_not(None))
            & (Request.urgent_seen_at.is_(None))
            & (Request.status.in_(OPEN)),
            0,
        ),
        else_=1,
    )


def mark_seen(request: Request) -> None:
    # Staff acted, so the urgent flag has been read.
    if request.urgent_flagged_at is not None and request.urgent_seen_at is None:
        request.urgent_seen_at = datetime.now(timezone.utc)


def aged_urgency_rank(now: datetime | None = None):
    now = now or datetime.now(timezone.utc)
    effective = func.coalesce(Request.final_urgency, Request.predicted_urgency)
    touched = _last_touched()
    waiting = Request.status.in_(WAITING)
    return case(
        (effective == Urgency.high, 0),
        ((effective == Urgency.medium) & waiting & (touched < now - AGE_MEDIUM), 0),
        (effective == Urgency.medium, 1),
        ((effective == Urgency.low) & waiting & (touched < now - AGE_LOW), 1),
        (effective == Urgency.low, 2),
        else_=3,
    )


def is_aged(urgency: Urgency | None, status: RequestStatus, waiting_since: datetime, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    if status not in WAITING:
        return False
    if urgency == Urgency.medium:
        return waiting_since < now - AGE_MEDIUM
    if urgency == Urgency.low:
        return waiting_since < now - AGE_LOW
    return False
