"""Pydantic schemas for appointments and work schedule."""
from datetime import date, time, datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel

from app.models.appointment import AppointmentStatus


# ---------------------------------------------------------------------------
# Work Schedule
# ---------------------------------------------------------------------------

class WorkScheduleItem(BaseModel):
    """Single day rule (weekly or override)."""
    day_of_week: Optional[int] = None       # 0=Mon..6=Sun
    specific_date: Optional[date] = None    # overrides weekly rule
    is_working: bool = True
    open_time: Optional[time] = None
    close_time: Optional[time] = None
    max_parallel: int = 1
    notes: Optional[str] = None


class WorkScheduleResponse(WorkScheduleItem):
    id: UUID
    tenant_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkScheduleSave(BaseModel):
    """Full weekly schedule (7 days) sent from frontend."""
    items: List[WorkScheduleItem]


class WorkScheduleOverride(BaseModel):
    """Override a specific date (holiday, sick day, etc.)."""
    specific_date: date
    is_working: bool
    open_time: Optional[time] = None
    close_time: Optional[time] = None
    max_parallel: int = 1
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Time slots
# ---------------------------------------------------------------------------

class TimeSlot(BaseModel):
    start: datetime
    end: datetime
    available: int      # how many spots left (max_parallel - booked)


# ---------------------------------------------------------------------------
# Appointment
# ---------------------------------------------------------------------------

class AppointmentCreate(BaseModel):
    customer_id: UUID
    service_id: Optional[UUID] = None
    scheduled_at: datetime
    notes: Optional[str] = None


class AppointmentUpdate(BaseModel):
    notes: Optional[str] = None


class CustomerBrief(BaseModel):
    id: UUID
    phone: str
    name: Optional[str] = None
    is_vip: bool

    model_config = {"from_attributes": True}


class ServiceBrief(BaseModel):
    id: UUID
    name_ar: str
    name_en: str
    name_ru: Optional[str] = None
    avg_duration_minutes: int

    model_config = {"from_attributes": True}


class AppointmentResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    customer: CustomerBrief
    service: Optional[ServiceBrief] = None
    scheduled_at: datetime
    status: AppointmentStatus
    reminder_sent: bool
    queue_entry_id: Optional[UUID] = None
    notes: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
