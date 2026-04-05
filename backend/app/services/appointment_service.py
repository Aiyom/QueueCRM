"""Appointment booking service — slots, booking, auto-enqueue, reminders."""
import uuid
from datetime import date, datetime, timedelta, timezone, time
from typing import Optional
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.models.appointment import Appointment, AppointmentStatus
from app.models.work_schedule import WorkSchedule
from app.models.service import Service
from app.models.customer import Customer
from app.models.tenant import Tenant
from app.schemas.appointment import TimeSlot

logger = structlog.get_logger(__name__)

# Timezone for Saudi Arabia
KSA_TZ = ZoneInfo("Asia/Riyadh")

# How far ahead clients can book (days)
MAX_BOOK_AHEAD_DAYS = 30


# ---------------------------------------------------------------------------
# Work schedule helpers
# ---------------------------------------------------------------------------


async def get_schedule_for_date(
    db: AsyncSession, tenant_id: uuid.UUID, target_date: date
) -> Optional[WorkSchedule]:
    """Return the effective WorkSchedule for a given date.

    specific_date overrides day_of_week.
    """
    # 1. Try specific_date override
    result = await db.execute(
        select(WorkSchedule).where(
            and_(
                WorkSchedule.tenant_id == tenant_id,
                WorkSchedule.specific_date == target_date,
            )
        )
    )
    override = result.scalar_one_or_none()
    if override:
        return override

    # 2. Fall back to weekly rule (Monday=0 … Sunday=6)
    dow = target_date.weekday()
    result = await db.execute(
        select(WorkSchedule).where(
            and_(
                WorkSchedule.tenant_id == tenant_id,
                WorkSchedule.day_of_week == dow,
                WorkSchedule.specific_date.is_(None),
            )
        )
    )
    return result.scalar_one_or_none()


async def get_working_days(
    db: AsyncSession, tenant_id: uuid.UUID, from_date: date, count: int = 7
) -> list[date]:
    """Return next `count` working days starting from from_date (inclusive)."""
    working = []
    current = from_date
    checked = 0
    while len(working) < count and checked < MAX_BOOK_AHEAD_DAYS:
        schedule = await get_schedule_for_date(db, tenant_id, current)
        if schedule and schedule.is_working and schedule.open_time and schedule.close_time:
            working.append(current)
        elif schedule is None:
            # No schedule configured at all — skip
            pass
        current += timedelta(days=1)
        checked += 1
    return working


# ---------------------------------------------------------------------------
# Slot calculation
# ---------------------------------------------------------------------------


async def get_available_slots(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    target_date: date,
    service_id: Optional[uuid.UUID] = None,
) -> list[TimeSlot]:
    """Return all available time slots for a given date and service."""
    schedule = await get_schedule_for_date(db, tenant_id, target_date)
    if not schedule or not schedule.is_working:
        return []
    if not schedule.open_time or not schedule.close_time:
        return []

    # Get service duration
    step_minutes = 30  # default
    if service_id:
        service = await db.get(Service, service_id)
        if service:
            step_minutes = service.avg_duration_minutes

    # Build all slots for the day
    tz = KSA_TZ
    open_dt = datetime.combine(target_date, schedule.open_time, tzinfo=tz)
    close_dt = datetime.combine(target_date, schedule.close_time, tzinfo=tz)

    slots: list[TimeSlot] = []
    current = open_dt
    now = datetime.now(tz)

    while current + timedelta(minutes=step_minutes) <= close_dt:
        slot_end = current + timedelta(minutes=step_minutes)

        # Skip slots in the past
        if slot_end <= now:
            current = slot_end
            continue

        # Count existing confirmed appointments overlapping this slot
        booked_count = await db.scalar(
            select(func.count()).where(
                and_(
                    Appointment.tenant_id == tenant_id,
                    Appointment.status == AppointmentStatus.confirmed,
                    Appointment.scheduled_at >= current,
                    Appointment.scheduled_at < slot_end,
                )
            )
        ) or 0

        available = schedule.max_parallel - booked_count
        if available > 0:
            slots.append(TimeSlot(
                start=current,
                end=slot_end,
                available=available,
            ))

        current = slot_end

    return slots


# ---------------------------------------------------------------------------
# Booking
# ---------------------------------------------------------------------------


async def create_appointment(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    customer_id: uuid.UUID,
    scheduled_at: datetime,
    service_id: Optional[uuid.UUID] = None,
    notes: Optional[str] = None,
) -> Appointment:
    """Create a confirmed appointment. Raises ValueError if slot is full."""
    # Verify slot is still available
    target_date = scheduled_at.astimezone(KSA_TZ).date()
    schedule = await get_schedule_for_date(db, tenant_id, target_date)
    if not schedule or not schedule.is_working:
        raise ValueError("Not a working day")

    step_minutes = 30
    if service_id:
        service = await db.get(Service, service_id)
        if service:
            step_minutes = service.avg_duration_minutes

    slot_end = scheduled_at + timedelta(minutes=step_minutes)
    booked = await db.scalar(
        select(func.count()).where(
            and_(
                Appointment.tenant_id == tenant_id,
                Appointment.status == AppointmentStatus.confirmed,
                Appointment.scheduled_at >= scheduled_at,
                Appointment.scheduled_at < slot_end,
            )
        )
    ) or 0

    if booked >= schedule.max_parallel:
        raise ValueError("Slot is fully booked")

    appointment = Appointment(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        customer_id=customer_id,
        service_id=service_id,
        scheduled_at=scheduled_at,
        status=AppointmentStatus.confirmed,
        notes=notes,
    )
    db.add(appointment)
    await db.flush()
    logger.info("Appointment created", appointment_id=str(appointment.id))
    return appointment


async def cancel_appointment(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    appointment_id: uuid.UUID,
) -> Appointment:
    """Cancel an appointment. Raises ValueError if not found or already done."""
    appt = await db.get(Appointment, appointment_id)
    if not appt or appt.tenant_id != tenant_id:
        raise ValueError("Appointment not found")
    if appt.status in (AppointmentStatus.done, AppointmentStatus.cancelled):
        raise ValueError(f"Cannot cancel appointment with status {appt.status}")
    appt.status = AppointmentStatus.cancelled
    return appt


# ---------------------------------------------------------------------------
# List for manager dashboard
# ---------------------------------------------------------------------------


async def list_appointments(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    target_date: Optional[date] = None,
    status: Optional[AppointmentStatus] = None,
) -> list[Appointment]:
    """List appointments with optional date and status filter."""
    filters = [Appointment.tenant_id == tenant_id]

    if target_date:
        tz = KSA_TZ
        day_start = datetime.combine(target_date, time.min, tzinfo=tz)
        day_end = datetime.combine(target_date, time.max, tzinfo=tz)
        filters.append(Appointment.scheduled_at >= day_start)
        filters.append(Appointment.scheduled_at <= day_end)

    if status:
        filters.append(Appointment.status == status)

    result = await db.execute(
        select(Appointment)
        .where(and_(*filters))
        .order_by(Appointment.scheduled_at)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Cron: auto-enqueue appointments
# ---------------------------------------------------------------------------


async def auto_enqueue_due_appointments(
    db: AsyncSession, redis: Redis
) -> None:
    """Called every 5 min. Moves confirmed appointments into live queue."""
    from app.services import queue_service

    now = datetime.now(timezone.utc)
    window_end = now + timedelta(minutes=5)

    result = await db.execute(
        select(Appointment).where(
            and_(
                Appointment.status == AppointmentStatus.confirmed,
                Appointment.queue_entry_id.is_(None),
                Appointment.scheduled_at >= now,
                Appointment.scheduled_at <= window_end,
            )
        )
    )
    appointments = list(result.scalars().all())

    for appt in appointments:
        try:
            entry = await queue_service.add_to_queue(
                db, redis,
                tenant_id=appt.tenant_id,
                customer_id=appt.customer_id,
                service_id=appt.service_id,
            )
            appt.queue_entry_id = entry.id
            logger.info(
                "Appointment auto-enqueued",
                appointment_id=str(appt.id),
                queue_entry_id=str(entry.id),
            )
        except Exception as exc:
            logger.error("Auto-enqueue failed", appointment_id=str(appt.id), error=str(exc))

    if appointments:
        await db.commit()


# ---------------------------------------------------------------------------
# Cron: send reminders
# ---------------------------------------------------------------------------


async def send_appointment_reminders(db: AsyncSession) -> None:
    """Called every 5 min. Sends reminder 1h before scheduled_at."""
    now = datetime.now(timezone.utc)
    window_start = now + timedelta(minutes=55)
    window_end = now + timedelta(minutes=65)

    result = await db.execute(
        select(Appointment).where(
            and_(
                Appointment.status == AppointmentStatus.confirmed,
                Appointment.reminder_sent == False,  # noqa: E712
                Appointment.scheduled_at >= window_start,
                Appointment.scheduled_at <= window_end,
            )
        )
    )
    appointments = list(result.scalars().all())

    for appt in appointments:
        try:
            tenant = await db.get(Tenant, appt.tenant_id)
            customer = await db.get(Customer, appt.customer_id)
            service = await db.get(Service, appt.service_id) if appt.service_id else None

            if not tenant or not customer:
                continue

            lang = customer.preferred_language or "ar"
            scheduled_local = appt.scheduled_at.astimezone(KSA_TZ)
            time_str = scheduled_local.strftime("%H:%M")
            service_name = ""
            if service:
                if lang == "ar":
                    service_name = service.name_ar
                elif lang == "ru":
                    service_name = service.name_ru or service.name_en or service.name_ar
                else:
                    service_name = service.name_en or service.name_ar

            msg = _reminder_msg(time_str, service_name, lang)

            # Send via Telegram if linked
            if customer.telegram_chat_id and tenant.telegram_bot_token:
                from app.services.telegram_service import send_message
                await send_message(
                    bot_token=tenant.telegram_bot_token,
                    chat_id=customer.telegram_chat_id,
                    text=msg,
                )

            # Send via WhatsApp if configured
            elif tenant.d360_api_key:
                from app.services.whatsapp_service import send_message as wa_send
                await wa_send(
                    d360_api_key=tenant.d360_api_key,
                    to_phone=customer.phone,
                    text=msg,
                )

            appt.reminder_sent = True
            logger.info("Appointment reminder sent", appointment_id=str(appt.id))

        except Exception as exc:
            logger.error("Reminder failed", appointment_id=str(appt.id), error=str(exc))

    if appointments:
        await db.commit()


def _reminder_msg(time_str: str, service_name: str, lang: str) -> str:
    svc = f" — {service_name}" if service_name else ""
    if lang == "ar":
        return f"⏰ تذكير: لديك موعد اليوم الساعة {time_str}{svc}. نراك قريباً!"
    if lang == "ru":
        return f"⏰ Напоминание: ваша запись сегодня в {time_str}{svc}. Ждём вас!"
    return f"⏰ Reminder: your appointment is today at {time_str}{svc}. See you soon!"
