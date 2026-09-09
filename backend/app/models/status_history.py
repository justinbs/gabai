import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import RequestStatus, request_status_enum


class StatusHistoryEntry(Base):
    __tablename__ = "status_history_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id"), nullable=False)
    request = relationship("Request", back_populates="status_history")

    from_status: Mapped[RequestStatus | None] = mapped_column(request_status_enum)
    to_status: Mapped[RequestStatus] = mapped_column(request_status_enum, nullable=False)

    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    actor = relationship("User", foreign_keys=[actor_id])

    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)