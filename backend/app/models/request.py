import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import EncryptedText
from app.models.enums import RequestStatus, Urgency, request_status_enum, urgency_enum


class Request(Base):
    __tablename__ = "requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)

    citizen_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    citizen = relationship("User", foreign_keys=[citizen_id])

    description: Mapped[str] = mapped_column(Text, nullable=False)

    predicted_category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))
    predicted_category = relationship("Category", foreign_keys=[predicted_category_id])
    predicted_urgency: Mapped[Urgency | None] = mapped_column(urgency_enum)
    category_confidence: Mapped[float | None] = mapped_column()
    urgency_confidence: Mapped[float | None] = mapped_column()

    final_category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))
    final_category = relationship("Category", foreign_keys=[final_category_id])
    final_urgency: Mapped[Urgency | None] = mapped_column(urgency_enum)

    status: Mapped[RequestStatus] = mapped_column(
        request_status_enum,
        nullable=False,
        default=RequestStatus.submitted,
    )
    assigned_staff_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    assigned_staff = relationship("User", foreign_keys=[assigned_staff_id])

    model_version: Mapped[str | None] = mapped_column(String(100))
    classified_at: Mapped[datetime | None] = mapped_column()

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now(), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column()
    # Set once retention has removed the text and attachments. See app/retention.py.
    redacted_at: Mapped[datetime | None] = mapped_column()

    # The resident marked it urgent, once, with a reason. Pins it to the top of
    # the staff queues; never changes the urgency label.
    urgent_flagged_at: Mapped[datetime | None] = mapped_column()
    urgent_reason: Mapped[str | None] = mapped_column(EncryptedText)

    status_history = relationship(
        "StatusHistoryEntry",
        back_populates="request",
        order_by="StatusHistoryEntry.created_at",
    )
    attachments = relationship(
        "Attachment",
        back_populates="request",
        order_by="Attachment.uploaded_at",
    )

    @property
    def category(self):
        return self.final_category or self.predicted_category

    @property
    def urgency(self):
        return self.final_urgency or self.predicted_urgency

    @property
    def waiting_since(self) -> datetime:
        # The last status change, or when it was submitted.
        times = [entry.created_at for entry in self.status_history]
        return max(times) if times else self.created_at

    @property
    def aged(self) -> bool:
        from app.queue_order import is_aged

        return is_aged(self.urgency, self.status, self.waiting_since)