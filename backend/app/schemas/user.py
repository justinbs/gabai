import uuid

from fastapi_users import schemas
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

from app.models.user import ApprovalStatus, Role


class UserRead(schemas.BaseUser[uuid.UUID]):
    full_name: str
    role: Role
    approval_status: ApprovalStatus
    residence: str | None
    must_change_password: bool


class UserCreate(schemas.BaseUserCreate):
    full_name: str
    residence: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    role: Role


class AdminUserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str = Field(min_length=1, max_length=150)
    role: Role


class AdminUserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    role: Role | None = None
    is_active: bool | None = None


class PaginatedUsers(BaseModel):
    items: list[UserRead]
    total: int
    limit: int
    offset: int


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class TemporaryPassword(BaseModel):
    temporary_password: str


class RegistrationDecision(BaseModel):
    approval_status: Literal["approved", "rejected"]
