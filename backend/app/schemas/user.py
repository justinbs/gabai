import uuid

from fastapi_users import schemas
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import Role


class UserRead(schemas.BaseUser[uuid.UUID]):
    full_name: str
    role: Role


class UserCreate(schemas.BaseUserCreate):
    full_name: str


class UserUpdate(schemas.BaseUserUpdate):
    full_name: str | None = None
    role: Role | None = None


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    role: Role


class AdminUserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
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