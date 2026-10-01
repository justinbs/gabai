from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.site_settings import THEMES

Theme = Literal[THEMES]


class SiteSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    barangay_name: str
    place: str
    address: str | None
    hotline: str | None
    office_hours: str | None
    theme: Theme
    logo_version: str | None
    terms_version: str
    updated_at: datetime


class SiteSettingsUpdate(BaseModel):
    # Only fields that were sent are applied, so a missing field is left alone
    # and an explicit null clears a contact detail.
    barangay_name: str | None = Field(default=None, min_length=1, max_length=100)
    place: str | None = Field(default=None, min_length=1, max_length=100)
    address: str | None = Field(default=None, max_length=200)
    hotline: str | None = Field(default=None, max_length=50)
    office_hours: str | None = Field(default=None, max_length=100)
    theme: Theme | None = None
