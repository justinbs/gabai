import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SignInFailure(Base):
    """A failed sign-in, kept only to count recent ones.

    A counter, not a record: rows older than the window can be deleted. The
    audit log keeps the lasting record. The typed email is never stored.
    """

    __tablename__ = "sign_in_failures"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Null when the email matched no account.
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    ip_address: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
