"""Classify a submitted request, then route it or send it for review.

Runs after the response, so the resident gets a reference number without waiting
on inference. It opens its own session: the request-scoped one is closed by the
time a background task runs.

No audit row and no notification on purpose. The audit log records what people
did and the status history records what happened, so a machine move belongs in
the second one only.

Known limit: a background task does not survive a restart and is not retried. A
request whose classification never runs stays in the review queue for a person,
so it is delayed, never lost. A review queue filling with `submitted` rows is
the signal that this is broken.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.inference import classifier
from app.models.enums import RequestStatus
from app.models.request import Request
from app.models.routing_rule import RoutingRule
from app.models.status_history import StatusHistoryEntry

settings = get_settings()
log = logging.getLogger(__name__)


async def _handler_for(db: AsyncSession, category_id: int):
    return (
        await db.execute(
            select(RoutingRule.staff_id).where(
                RoutingRule.category_id == category_id,
                RoutingRule.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()


async def classify_and_route(request_id: int) -> None:
    async with AsyncSessionLocal() as db:
        request = await db.get(Request, request_id)
        # A human may have got there first, so only touch untouched requests.
        if request is None or request.status != RequestStatus.submitted:
            return

        try:
            prediction = await run_in_threadpool(
                classifier.classify, request.description
            )
        except Exception:
            # Leave it at `submitted`. Staff still see it, because that status is
            # in the scope filter for exactly this reason.
            log.exception("classification failed for request %s", request_id)
            return

        request.predicted_category_id = prediction.category_id
        request.predicted_urgency = prediction.urgency
        request.category_confidence = prediction.category_confidence
        request.urgency_confidence = prediction.urgency_confidence
        request.model_version = prediction.model_version
        request.classified_at = datetime.now(timezone.utc)

        # Delta a2. The lower of the two confidences decides, because being sure
        # of the category but not the urgency is still not safe to route alone.
        confidence = min(prediction.category_confidence, prediction.urgency_confidence)
        handler = None
        if confidence >= settings.confidence_threshold and prediction.category_id:
            handler = await _handler_for(db, prediction.category_id)

        if handler is None:
            request.status = RequestStatus.under_review
        else:
            request.status = RequestStatus.routed
            request.assigned_staff_id = handler

        # actor_id stays null: the system made this move, not a person.
        db.add(
            StatusHistoryEntry(
                request_id=request.id,
                from_status=RequestStatus.submitted,
                to_status=request.status,
                actor_id=None,
                note=None,
            )
        )

        await db.commit()
