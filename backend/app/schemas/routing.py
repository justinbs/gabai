import uuid

from pydantic import BaseModel, ConfigDict

from app.schemas.category import CategoryRead
from app.schemas.user import UserSummary


class RoutingRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: CategoryRead
    staff: UserSummary
    is_active: bool


class RoutingRuleInput(BaseModel):
    category_id: int
    staff_id: uuid.UUID


class RoutingRulesReplace(BaseModel):
    rules: list[RoutingRuleInput]