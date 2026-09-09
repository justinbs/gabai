import enum

from sqlalchemy import Enum as SAEnum


class Urgency(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class RequestStatus(str, enum.Enum):
    submitted = "submitted"
    classified = "classified"
    routed = "routed"
    under_review = "under_review"
    in_progress = "in_progress"
    resolved = "resolved"
    closed = "closed"


urgency_enum = SAEnum(Urgency, name="urgency")
request_status_enum = SAEnum(RequestStatus, name="request_status")