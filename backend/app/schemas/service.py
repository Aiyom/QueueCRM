"""Service-related Pydantic schemas."""
import uuid
from pydantic import BaseModel


class ServiceCreate(BaseModel):
    name_ar: str
    name_en: str
    name_ru: str | None = None
    avg_duration_minutes: int = 30
    sort_order: int = 0


class ServiceUpdate(BaseModel):
    name_ar: str | None = None
    name_en: str | None = None
    name_ru: str | None = None
    avg_duration_minutes: int | None = None
    is_active: bool | None = None
    sort_order: int | None = None


class ServiceResponse(BaseModel):
    id: uuid.UUID
    name_ar: str
    name_en: str
    name_ru: str | None = None
    avg_duration_minutes: int
    is_active: bool
    sort_order: int

    model_config = {"from_attributes": True}
