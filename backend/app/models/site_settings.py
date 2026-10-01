from datetime import datetime

from sqlalchemy import CheckConstraint, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Allowed theme names. The colours are defined in the frontend.
THEMES = ("green", "blue", "maroon", "teal", "purple", "brown")


class SiteSettings(Base):
    """The barangay's details and the site's look. Always exactly one row, id 1."""

    __tablename__ = "site_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_site_settings_single_row"),
        CheckConstraint(
            "theme IN (" + ", ".join(f"'{t}'" for t in THEMES) + ")",
            name="ck_site_settings_theme",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    barangay_name: Mapped[str] = mapped_column(String(100), nullable=False)
    place: Mapped[str] = mapped_column(String(100), nullable=False)
    address: Mapped[str | None] = mapped_column(String(200))
    hotline: Mapped[str | None] = mapped_column(String(50))
    office_hours: Mapped[str | None] = mapped_column(String(100))
    theme: Mapped[str] = mapped_column(String(10), nullable=False, server_default="green")
    # Relative to the uploads folder. Null means use the default logo.
    logo_path: Mapped[str | None] = mapped_column(String(255))
    # Changes on every upload so browsers don't show a cached logo.
    logo_version: Mapped[str | None] = mapped_column(String(40))
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )
