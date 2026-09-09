from sqlalchemy import or_

from app.models.enums import RequestStatus
from app.models.request import Request
from app.models.user import Role, User


def request_scope_filter(user: User):
    # citizen -> only their own. staff -> assigned to them, or anything
    # awaiting review. admin -> everything.
    if user.role == Role.admin:
        return None
    if user.role == Role.staff:
        return or_(
            Request.assigned_staff_id == user.id,
            Request.status == RequestStatus.under_review,
        )
    return Request.citizen_id == user.id