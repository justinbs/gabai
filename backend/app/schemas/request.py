from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RequestStatus, Urgency
from app.schemas.attachment import AttachmentRead
from app.schemas.category import CategoryRead
from app.schemas.user import UserSummary


class RequestCreate(BaseModel):
    description: str = Field(min_length=10, max_length=5000)


class StatusUpdate(BaseModel):
    to_status: Literal["in_progress", "resolved", "closed"]
    note: str | None = Field(default=None, max_length=2000)


class ReviewDecision(BaseModel):
    final_category_id: int
    final_urgency: Urgency
    note: str | None = Field(default=None, max_length=2000)


class StatusHistoryEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    from_status: RequestStatus | None
    to_status: RequestStatus
    actor: UserSummary | None
    note: str | None
    created_at: datetime


class RequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reference_number: str
    citizen: UserSummary
    description: str
    predicted_category: CategoryRead | None
    predicted_urgency: Urgency | None
    category_confidence: float | None
    urgency_confidence: float | None
    final_category: CategoryRead | None
    final_urgency: Urgency | None
    category: CategoryRead | None
    urgency: Urgency | None
    status: RequestStatus
    assigned_staff: UserSummary | None
    model_version: str | None
    classified_at: datetime | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    attachments: list[AttachmentRead]
    status_history: list[StatusHistoryEntryRead]


class RequestSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reference_number: str
    description: str
    category: CategoryRead | None
    urgency: Urgency | None
    category_confidence: float | None
    urgency_confidence: float | None
    status: RequestStatus
    assigned_staff: UserSummary | None
    created_at: datetime


class PaginatedRequests(BaseModel):
    items: list[RequestSummary]
    total: int
    limit: int
    offset: int