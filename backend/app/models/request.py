import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
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