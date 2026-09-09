from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.schemas.user import UserSummary


class AuditLogEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor: UserSummary | None
    action: str
    object_type: str
    object_id: str | None
    detail: dict[str, Any] | None
    ip_address: str | None
    created_at: datetime


class PaginatedAuditLog(BaseModel):
    items: list[AuditLogEntryRead]
    total: int
    limit: int
    offset: int