from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import RequestStatus, Urgency
from app.schemas.attachment import AttachmentRead
from app.schemas.category import CategoryRead
from app.schemas.user import UserSummary


class RequestCreate(BaseModel):
    description: str = Field(min_length=10, max_length=5000)
    # Required only once the admin has listed puroks or streets.
    location_id: int | None = None


class LocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_active: bool
    sort_order: int


class LocationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    sort_order: int = 0


class LocationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    is_active: bool | None = None
    sort_order: int | None = None


class RequestRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reference_number: str


class DuplicateLink(BaseModel):
    reference_number: str = Field(min_length=1, max_length=20)


class SuggestionDecision(BaseModel):
    decision: Literal["dismissed"]


class DuplicateCandidate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reference_number: str
    description: str
    status: RequestStatus
    created_at: datetime


class DuplicateSuggestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    score: float
    candidate: DuplicateCandidate


class SameProblemReport(DuplicateCandidate):
    score: float
    # Enough words in common to be ticked for linking at the start.
    likely: bool


class LinkReports(BaseModel):
    request_ids: list[int] = Field(min_length=1, max_length=200)
    # Listed as likely but unticked: not the same problem, so not suggested again.
    not_same: list[int] = Field(default_factory=list, max_length=200)


class SkippedReport(BaseModel):
    id: int
    reference_number: str
    reason: str


class LinkReportsResult(BaseModel):
    linked: list[RequestRef]
    skipped: list[SkippedReport]


class Surge(BaseModel):
    category: CategoryRead
    location: LocationRead | None
    count: int
    since: datetime
    # The report to open and link the others to.
    main: RequestRef | None


class StatusUpdate(BaseModel):
    to_status: Literal["in_progress", "resolved", "closed"]
    note: str | None = Field(default=None, max_length=2000)


class UrgentFlag(BaseModel):
    reason: str = Field(min_length=1, max_length=200)

    @field_validator("reason")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Say why it's urgent")
        return value


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


class AgencyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str | None
    hours: str | None
    website: str | None
    notes: str | None
    is_active: bool
    sort_order: int


class AgencyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    sort_order: int = 0


class AgencyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=50)
    hours: str | None = Field(default=None, max_length=100)
    website: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=300)
    is_active: bool | None = None
    sort_order: int | None = None

    @field_validator("website")
    @classmethod
    def web_address(cls, value):
        # Shown as a link to residents, so only http(s).
        if value and value.strip() and not value.strip().lower().startswith(("http://", "https://")):
            raise ValueError("The website must start with http:// or https://")
        return value



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
    urgent_flagged_at: datetime | None
    urgent_reason: str | None
    urgent_pinned: bool
    waiting_since: datetime
    aged: bool
    location: LocationRead | None
    duplicate_of: RequestRef | None
    linked_reports: list[RequestRef]
    linked_count: int
    attachments: list[AttachmentRead]
    status_history: list[StatusHistoryEntryRead]
    referred_agency: AgencyRead | None = None
    referred_at: datetime | None = None 
    referral_note: str | None = None 

class ReferralCreate(BaseModel):
    agency_id: int
    note: str | None = Field(default=None, max_length=500)


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
    urgent_flagged_at: datetime | None
    urgent_pinned: bool
    waiting_since: datetime
    aged: bool
    location: LocationRead | None
    duplicate_of: RequestRef | None
    linked_count: int
    referred_agency: AgencyRead | None = None


class PaginatedRequests(BaseModel):
    items: list[RequestSummary]
    total: int
    limit: int
    offset: int