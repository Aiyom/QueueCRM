"""Queue-related Pydantic schemas."""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel

from app.models.queue_entry import QueueStatus


class CustomerBrief(BaseModel):
    id: uuid.UUID
    phone: str
    name: Optional[str] = None
    is_vip: bool


class ServiceBrief(BaseModel):
    id: uuid.UUID
    name_ar: str
    name_en: str


class QueueEntryResponse(BaseModel):
    id: uuid.UUID
    position: int
    status: QueueStatus
    eta_minutes: float
    customer: CustomerBrief
    service: Optional[ServiceBrief] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class QueueEntryDetail(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    customer_id: uuid.UUID
    service_id: Optional[uuid.UUID] = None
    status: QueueStatus
    position: Optional[int] = None
    called_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    amount: Optional[Decimal] = None
    notes: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AddToQueueRequest(BaseModel):
    customer_id: uuid.UUID
    service_id: Optional[uuid.UUID] = None


class FinishServiceRequest(BaseModel):
    amount: Optional[float] = None
    notes: Optional[str] = None


class QueueStatsResponse(BaseModel):
    total_waiting: int
    total_called: int
    total_in_service: int
    avg_wait_time_minutes: float
    is_accepting_queue: bool
