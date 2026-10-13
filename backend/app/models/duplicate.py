import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Float, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DuplicateSuggestion(Base):
    """A newer report that may describe the same problem as an older open one.

    Staff decide: link it, or say it's not a duplicate. Stored, so a dismissed
    suggestion stays dismissed.
    """

    __tablename__ = "duplicate_suggestions"
    __table_args__ = (
        UniqueConstraint("request_id", "candidate_id", name="uq_duplicate_suggestion_pair"),
        CheckConstraint("decision IS NULL OR decision IN ('linked', 'dismissed')", name="ck_duplicate_decision"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id"), nullable=False)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("requests.id"), nullable=False)
    candidate = relationship("Request", foreign_keys=[candidate_id])
    score: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    decision: Mapped[str | None] = mapped_column(String(10))
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    decided_at: Mapped[datetime | None] = mapped_column()
