from sqlalchemy import Boolean, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Location(Base):
    """A purok or street the admin lists, for "Where is the problem?".

    Optional: until the admin adds one, the submit form doesn't ask. Never
    deleted, only switched off, so old requests keep pointing at a real row.
    """

    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
