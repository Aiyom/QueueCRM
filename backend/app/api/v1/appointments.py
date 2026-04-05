"""Appointments and work schedule API."""
import uuid
from datetime import date, datetime
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, and_

from app.core.deps import DBSession, TenantUser, TenantAdmin, get_tenant_id
from app.models.appointment import Appointment, AppointmentStatus
from app.models.work_schedule import WorkSchedule
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentResponse,
    TimeSlot,
    WorkScheduleResponse,
    WorkScheduleSave,
    WorkScheduleOverride,
)
from app.services import appointment_service

router = APIRouter(tags=["appointments"])


# ---------------------------------------------------------------------------
# Work schedule
# ---------------------------------------------------------------------------


@router.get("/work-schedule/", response_model=List[WorkScheduleResponse])
async def get_work_schedule(payload: TenantUser, db: DBSession):
    """Return all work schedule rules for this tenant."""
    tenant_id = get_tenant_id(payload)
    result = await db.execute(
        select(WorkSchedule)
        .where(WorkSchedule.tenant_id == tenant_id)
        .order_by(WorkSchedule.day_of_week, WorkSchedule.specific_date)
    )
    return list(result.scalars().all())


@router.put("/work-schedule/", response_model=List[WorkScheduleResponse])
async def save_work_schedule(
    body: WorkScheduleSave,
    payload: TenantAdmin,
    db: DBSession,
):
    """Replace weekly schedule (7 day_of_week rules)."""
    tenant_id = get_tenant_id(payload)

    # Delete existing weekly rules (not overrides)
    result = await db.execute(
        select(WorkSchedule).where(
            and_(
                WorkSchedule.tenant_id == tenant_id,
                WorkSchedule.specific_date.is_(None),
            )
        )
    )
    for ws in result.scalars().all():
        await db.delete(ws)

    created = []
    for item in body.items:
        ws = WorkSchedule(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            day_of_week=item.day_of_week,
            specific_date=None,
            is_working=item.is_working,
            open_time=item.open_time,
            close_time=item.close_time,
            max_parallel=item.max_parallel,
            notes=item.notes,
        )
        db.add(ws)
        created.append(ws)

    await db.commit()
    for ws in created:
        await db.refresh(ws)
    return created


@router.post("/work-schedule/override", response_model=WorkScheduleResponse)
async def add_schedule_override(
    body: WorkScheduleOverride,
    payload: TenantAdmin,
    db: DBSession,
):
    """Add or replace a specific-date override (holiday, sick day, etc.)."""
    tenant_id = get_tenant_id(payload)

    # Remove existing override for this date if any
    result = await db.execute(
        select(WorkSchedule).where(
            and_(
                WorkSchedule.tenant_id == tenant_id,
                WorkSchedule.specific_date == body.specific_date,
            )
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        await db.delete(existing)

    ws = WorkSchedule(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        specific_date=body.specific_date,
        day_of_week=None,
        is_working=body.is_working,
        open_time=body.open_time,
        close_time=body.close_time,
        max_parallel=body.max_parallel,
        notes=body.notes,
    )
    db.add(ws)
    await db.commit()
    await db.refresh(ws)
    return ws


@router.delete("/work-schedule/override/{target_date}", status_code=204)
async def delete_schedule_override(
    target_date: date,
    payload: TenantAdmin,
    db: DBSession,
):
    """Remove a specific-date override (restore to weekly default)."""
    tenant_id = get_tenant_id(payload)
    result = await db.execute(
        select(WorkSchedule).where(
            and_(
                WorkSchedule.tenant_id == tenant_id,
                WorkSchedule.specific_date == target_date,
            )
        )
    )
    ws = result.scalar_one_or_none()
    if ws:
        await db.delete(ws)
        await db.commit()


# ---------------------------------------------------------------------------
# Slots
# ---------------------------------------------------------------------------


@router.get("/appointments/slots", response_model=List[TimeSlot])
async def get_slots(
    payload: TenantUser,
    db: DBSession,
    target_date: date = Query(...),
    service_id: Optional[uuid.UUID] = Query(None),
):
    """Return available time slots for a given date."""
    tenant_id = get_tenant_id(payload)
    return await appointment_service.get_available_slots(
        db, tenant_id, target_date, service_id
    )


@router.get("/appointments/working-days", response_model=List[date])
async def get_working_days(
    payload: TenantUser,
    db: DBSession,
    from_date: date = Query(default_factory=date.today),
    count: int = Query(default=7, le=30),
):
    """Return next N working days (for bot date picker)."""
    tenant_id = get_tenant_id(payload)
    return await appointment_service.get_working_days(db, tenant_id, from_date, count)


# ---------------------------------------------------------------------------
# Appointments CRUD
# ---------------------------------------------------------------------------


@router.get("/appointments/", response_model=List[AppointmentResponse])
async def list_appointments(
    payload: TenantUser,
    db: DBSession,
    target_date: Optional[date] = Query(None),
    status: Optional[AppointmentStatus] = Query(None),
):
    """List appointments for manager dashboard."""
    tenant_id = get_tenant_id(payload)
    items = await appointment_service.list_appointments(db, tenant_id, target_date, status)

    # Eagerly load relationships for response
    responses = []
    for appt in items:
        await db.refresh(appt, ["customer", "service"])
        responses.append(appt)
    return responses


@router.post("/appointments/", response_model=AppointmentResponse, status_code=201)
async def create_appointment(
    body: AppointmentCreate,
    payload: TenantAdmin,
    db: DBSession,
):
    """Create appointment from manager dashboard."""
    tenant_id = get_tenant_id(payload)
    try:
        appt = await appointment_service.create_appointment(
            db,
            tenant_id=tenant_id,
            customer_id=body.customer_id,
            scheduled_at=body.scheduled_at,
            service_id=body.service_id,
            notes=body.notes,
        )
        await db.commit()
        await db.refresh(appt, ["customer", "service"])
        return appt
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@router.patch("/appointments/{appointment_id}/cancel", response_model=AppointmentResponse)
async def cancel_appointment(
    appointment_id: uuid.UUID,
    payload: TenantUser,
    db: DBSession,
):
    """Cancel an appointment."""
    tenant_id = get_tenant_id(payload)
    try:
        appt = await appointment_service.cancel_appointment(db, tenant_id, appointment_id)
        await db.commit()
        await db.refresh(appt, ["customer", "service"])
        return appt
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
