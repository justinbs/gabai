from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base. Alembic autogenerate reads metadata from here."""
