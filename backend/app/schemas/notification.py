from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_id: int | None
    reference_number: str | None
    message: str
    is_read: bool
    created_at: datetime


class PaginatedNotifications(BaseModel):
    items: list[NotificationRead]
    total: int
    limit: int
    offset: int
    unread_count: int