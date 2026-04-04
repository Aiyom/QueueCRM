"""Customer-related Pydantic schemas."""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


class CustomerCreate(BaseModel):
    phone: str = Field(..., pattern=r"^\+\d{10,15}$")
    name: Optional[str] = None
    notes: Optional[str] = None
    is_vip: bool = False


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    notes: Optional[str] = None
    is_vip: Optional[bool] = None


class CustomerResponse(BaseModel):
    id: uuid.UUID
    phone: str
    name: Optional[str] = None
    notes: Optional[str] = None
    is_vip: bool
    vip_set_manually: bool
    total_visits: int
    total_spent: Decimal
    preferred_language: str
    last_seen_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CustomerListResponse(BaseModel):
    items: list[CustomerResponse]
    total: int
    page: int
    page_size: int


class SegmentStatsResponse(BaseModel):
    total_customers: int
    vip_customers: int
    new_this_month: int
    avg_visits: float
    avg_spent: float
