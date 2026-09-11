from sqlalchemy import func as sqlfunc, or_, select

from app.models.enums import RequestStatus
from app.models.request import Request
from app.models.routing_rule import RoutingRule
from app.models.user import Role, User

# A request that has not been classified, or whose classification failed, has no
# category and nobody assigned. Without this it would be invisible to every staff
# member and reachable only by an admin, so it is a safety net: a request must
# never fall out of everyone's view.
AWAITING_HUMAN = (RequestStatus.submitted, RequestStatus.under_review)


def request_scope_filter(user: User):
    # citizen -> only their own. admin -> everything. staff -> assigned to them,
    # or in a category they handle, or waiting on a human. The category arm
    # matters because deactivating a routing rule would otherwise revoke a staff
    # member's access to requests already assigned to them.
    if user.role == Role.admin:
        return None
    if user.role == Role.staff:
        handled_categories = (
            select(RoutingRule.category_id)
            .where(RoutingRule.staff_id == user.id, RoutingRule.is_active.is_(True))
            .scalar_subquery()
        )
        effective_category = sqlfunc.coalesce(
            Request.final_category_id, Request.predicted_category_id
        )
        return or_(
            Request.assigned_staff_id == user.id,
            effective_category.in_(handled_categories),
            Request.status.in_(AWAITING_HUMAN),
        )
    return Request.citizen_id == user.id
