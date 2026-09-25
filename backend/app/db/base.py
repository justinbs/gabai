from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base. Alembic autogenerate reads metadata from here."""

    # Every timestamp carries its time zone, so the API sends 2026-09-25T20:37Z
    # rather than a bare time a browser would read as local.
    type_annotation_map = {datetime: DateTime(timezone=True)}
