import enum
from datetime import datetime

from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID
from sqlalchemy import Boolean, Enum as SAEnum, String, false, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Role(str, enum.Enum):
    citizen = "citizen"
    staff = "staff"
    admin = "admin"


class ApprovalStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "users"

    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    role: Mapped[Role] = mapped_column(SAEnum(Role, name="role"), nullable=False, default=Role.citizen)
    # Residents wait for staff to confirm they live in the barangay. The
    # default is pending so any path that forgets to set it fails closed.
    approval_status: Mapped[ApprovalStatus] = mapped_column(
        # The CHECK constraint lives in the migration, not here.
        SAEnum(ApprovalStatus, native_enum=False, length=10),
        nullable=False,
        default=ApprovalStatus.pending,
        server_default=text("'pending'"),
    )
    # Purok or street, typed at sign-up. Only there for that check.
    residence: Mapped[str | None] = mapped_column(String(150), nullable=True)
    # Set when an admin chose the password, so the admin knows it. Cleared when
    # the person picks their own.
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)