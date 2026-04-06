"""WhatsApp bot state machine with live queue + appointment booking."""
import uuid
import re
from datetime import date, datetime, timezone, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.models.customer import Customer
from app.models.queue_entry import QueueEntry, QueueStatus
from app.models.service import Service
from app.models.tenant import Tenant
from app.models.whatsapp_session import WhatsAppSession, SessionState
from app.models.appointment import Appointment, AppointmentStatus
from app.services import queue_service, whatsapp_service, appointment_service

logger = structlog.get_logger(__name__)

SESSION_TTL_HOURS = 24
CANCEL_KEYWORDS = {"إلغاء", "cancel", "الغاء", "يلغي", "إلغى", "отмена", "отменить"}
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
KSA_TZ = ZoneInfo("Asia/Riyadh")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_or_create_session(db, tenant_id, customer_id) -> WhatsAppSession:
    result = await db.execute(
        select(WhatsAppSession).where(
            and_(WhatsAppSession.tenant_id == tenant_id,
                 WhatsAppSession.customer_id == customer_id)
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        session = WhatsAppSession(
            id=uuid.uuid4(), tenant_id=tenant_id, customer_id=customer_id,
            state=SessionState.idle, context={},
            expires_at=datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS),
        )
        db.add(session)
    else:
        if session.expires_at < datetime.now(timezone.utc):
            session.state = SessionState.idle
            session.context = {}
        session.expires_at = datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)
    return session


async def _get_or_create_customer(db, tenant_id, phone, lang) -> Customer:
    result = await db.execute(
        select(Customer).where(and_(Customer.tenant_id == tenant_id, Customer.phone == phone))
    )
    customer = result.scalar_one_or_none()
    if not customer:
        customer = Customer(
            id=uuid.uuid4(), tenant_id=tenant_id, phone=phone, preferred_language=lang,
        )
        db.add(customer)
        await db.flush()
    else:
        customer.preferred_language = lang
    return customer


def _detect_language(text: str, enabled: list[str]) -> str:
    enabled = enabled or ["ar", "en"]
    arabic = sum(1 for c in text if "\u0600" <= c <= "\u06ff")
    cyrillic = sum(1 for c in text if "\u0400" <= c <= "\u04ff")
    if arabic > len(text) * 0.2 and "ar" in enabled:
        return "ar"
    if cyrillic > len(text) * 0.2 and "ru" in enabled:
        return "ru"
    return "en" if "en" in enabled else enabled[0]


async def _get_active_services(db, tenant_id) -> list[Service]:
    result = await db.execute(
        select(Service)
        .where(and_(Service.tenant_id == tenant_id, Service.is_active == True))  # noqa: E712
        .order_by(Service.sort_order)
    )
    return list(result.scalars().all())


def _service_names(services, lang) -> list[str]:
    if lang == "ar":
        return [s.name_ar for s in services]
    if lang == "ru":
        return [s.name_ru or s.name_en or s.name_ar for s in services]
    return [s.name_en or s.name_ar for s in services]


async def _get_active_queue_entry(db, tenant_id, customer_id) -> Optional[QueueEntry]:
    result = await db.execute(
        select(QueueEntry).where(
            and_(QueueEntry.tenant_id == tenant_id,
                 QueueEntry.customer_id == customer_id,
                 QueueEntry.status.in_([QueueStatus.waiting, QueueStatus.called]))
        )
    )
    return result.scalar_one_or_none()


def _main_menu_text(lang: str) -> str:
    menu = {
        "ar": "مرحباً! 👋\n1️⃣ الطابور الحالي\n2️⃣ حجز موعد مسبق\n3️⃣ مواعيدي\n\nأرسل رقم خيارك:",
        "ru": "Привет! 👋\n1️⃣ Живая очередь\n2️⃣ Записаться\n3️⃣ Мои записи\n\nОтправьте номер:",
        "en": "Hello! 👋\n1️⃣ Live Queue\n2️⃣ Book Appointment\n3️⃣ My Appointments\n\nSend the number:",
    }
    return menu.get(lang, menu["en"])


def _format_working_days(days: list, lang: str) -> str:
    """Text list of working days for WhatsApp."""
    lines = []
    for i, d in enumerate(days):
        dt = datetime.strptime(str(d), "%Y-%m-%d")
        label = dt.strftime("%-d %b %Y")
        lines.append(f"{i+1}. {label}")
    header = {
        "ar": "📅 اختر التاريخ:\n\n",
        "ru": "📅 Выберите дату:\n\n",
        "en": "📅 Choose a date:\n\n",
    }.get(lang, "📅 Choose a date:\n\n")
    return header + "\n".join(lines)


def _format_slots(slots: list, lang: str) -> str:
    """Text list of time slots for WhatsApp."""
    lines = []
    for i, slot in enumerate(slots):
        start = slot.start if hasattr(slot, "start") else slot["start"]
        dt = datetime.fromisoformat(start).astimezone(KSA_TZ)
        available = slot.available if hasattr(slot, "available") else slot["available"]
        lines.append(f"{i+1}. {dt.strftime('%H:%M')} ({available} {'مكان' if lang=='ar' else ('мест' if lang=='ru' else 'left')})")
    header = {
        "ar": "⏰ الأوقات المتاحة:\n\n",
        "ru": "⏰ Доступное время:\n\n",
        "en": "⏰ Available slots:\n\n",
    }.get(lang, "⏰ Available slots:\n\n")
    return header + "\n".join(lines)


# ---------------------------------------------------------------------------
# Main handler
# ---------------------------------------------------------------------------

async def handle_message(
    db: AsyncSession, redis: Redis, *, tenant: Tenant, phone: str, message_text: str
) -> None:
    text = message_text.strip()
    enabled = tenant.enabled_languages or ["ar", "en"]
    lang = _detect_language(text, enabled)
    d360_api_key = tenant.d360_api_key or ""

    customer = await _get_or_create_customer(db, tenant.id, phone, lang)
    session = await _get_or_create_session(db, tenant.id, customer.id)

    reply, services_for_list = await _dispatch(db, redis, tenant, customer, session, text, lang)
    await db.commit()

    if not d360_api_key:
        return

    if services_for_list is not None:
        await whatsapp_service.send_interactive_list(
            d360_api_key=d360_api_key, to_phone=phone,
            body_text=reply or whatsapp_service.msg_welcome(_service_names(services_for_list, lang), lang),
            services=services_for_list, lang=lang,
        )
    elif reply:
        await whatsapp_service.send_message(d360_api_key=d360_api_key, to_phone=phone, text=reply)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

async def _dispatch(db, redis, tenant, customer, session, text, lang) -> tuple[Optional[str], Optional[list]]:
    state = session.state
    text_lower = text.lower().strip()

    # --- IDLE → main menu ---
    if state == SessionState.idle:
        if text_lower in ("1", "queue", "طابور", "очередь"):
            return await _start_queue(db, tenant, customer, session, lang)
        if text_lower in ("2", "book", "حجز", "записаться", "запись"):
            return await _start_booking(db, tenant, session, lang)
        if text_lower in ("3", "my", "مواعيدي", "мои записи", "мои"):
            return await _show_my_appointments(db, tenant, customer, session, lang)
        # Any other message → show main menu
        return (_main_menu_text(lang), None)

    # --- BOOKING: DATE ---
    if state == SessionState.booking_date:
        days = session.context.get("booking_days", [])
        if text_lower in CANCEL_KEYWORDS:
            session.state = SessionState.idle
            return (_main_menu_text(lang), None)
        if text.isdigit():
            idx = int(text) - 1
            if 0 <= idx < len(days):
                chosen_date = days[idx]
                session.context = {**session.context, "booking_date": chosen_date}
                services = await _get_active_services(db, tenant.id)
                if not services:
                    return (_no_services(lang), None)
                session.state = SessionState.booking_service
                session.context = {**session.context, "service_ids": [str(s.id) for s in services]}
                return (whatsapp_service.msg_welcome(_service_names(services, lang), lang), services)
        return (_format_working_days(days, lang), None)

    # --- BOOKING: SERVICE ---
    if state == SessionState.booking_service:
        service_ids = session.context.get("service_ids", [])
        selected = None
        if UUID_RE.match(text):
            selected = await db.get(Service, uuid.UUID(text))
        elif text.isdigit():
            idx = int(text) - 1
            if 0 <= idx < len(service_ids):
                selected = await db.get(Service, uuid.UUID(service_ids[idx]))
        if text_lower in CANCEL_KEYWORDS:
            session.state = SessionState.idle
            return (_main_menu_text(lang), None)
        if selected:
            session.context = {**session.context, "booking_service_id": str(selected.id)}
            session.state = SessionState.booking_time
            return await _show_slots(db, tenant, session, lang)
        services = await _get_active_services(db, tenant.id)
        return (whatsapp_service.msg_welcome(_service_names(services, lang), lang), services)

    # --- BOOKING: TIME ---
    if state == SessionState.booking_time:
        if text_lower in CANCEL_KEYWORDS:
            session.state = SessionState.idle
            return (_main_menu_text(lang), None)
        slots = session.context.get("booking_slots", [])
        if text.isdigit():
            idx = int(text) - 1
            if 0 <= idx < len(slots):
                slot_start = slots[idx]
                return await _confirm_booking(db, redis, tenant, customer, session, slot_start, lang)
        return (_format_slots_from_context(slots, lang), None)

    # --- MY APPOINTMENTS ---
    if state == SessionState.my_appointments:
        if text_lower in CANCEL_KEYWORDS or text_lower == "back":
            session.state = SessionState.idle
            return (_main_menu_text(lang), None)
        appt_ids = session.context.get("appt_ids", [])
        if text.isdigit():
            idx = int(text) - 1
            if 0 <= idx < len(appt_ids):
                appt_id = uuid.UUID(appt_ids[idx])
                return await _cancel_appointment(db, tenant, customer, session, appt_id, lang)
        return await _show_my_appointments(db, tenant, customer, session, lang)

    # --- LIVE QUEUE STATES ---
    if state == SessionState.selecting_service:
        service_ids = session.context.get("service_ids", [])
        selected = None
        if UUID_RE.match(text):
            selected = await db.get(Service, uuid.UUID(text))
        elif text.isdigit():
            idx = int(text) - 1
            if 0 <= idx < len(service_ids):
                selected = await db.get(Service, uuid.UUID(service_ids[idx]))
        else:
            services = await _get_active_services(db, tenant.id)
            tl = text.lower()
            for svc in services:
                if tl in svc.name_ar.lower() or tl in (svc.name_en or "").lower() or tl in (svc.name_ru or "").lower():
                    selected = svc
                    break

        if not selected:
            return (whatsapp_service.msg_invalid_service(lang), None)

        existing = await _get_active_queue_entry(db, tenant.id, customer.id)
        if existing:
            return (whatsapp_service.msg_already_in_queue(lang), None)

        entry = await queue_service.add_to_queue(
            db, redis, tenant_id=tenant.id, customer_id=customer.id, service_id=selected.id,
        )
        position = await queue_service.get_queue_position(redis, tenant.id, entry.id)
        eta = (position or 1) * selected.avg_duration_minutes
        session.state = SessionState.in_queue
        session.context = {**session.context, "entry_id": str(entry.id)}
        return (whatsapp_service.msg_queued(position or 1, eta, lang), None)

    if state == SessionState.in_queue:
        if text_lower in CANCEL_KEYWORDS:
            entry_id_str = session.context.get("entry_id")
            if entry_id_str:
                try:
                    await queue_service.cancel_entry(db, redis, tenant.id, uuid.UUID(entry_id_str))
                except ValueError:
                    pass
            session.state = SessionState.idle
            session.context = {}
            return (whatsapp_service.msg_cancelled(lang), None)
        entry_id_str = session.context.get("entry_id")
        if entry_id_str:
            position = await queue_service.get_queue_position(redis, tenant.id, uuid.UUID(entry_id_str))
            if position:
                return (whatsapp_service.msg_info(position, position * 20, lang), None)
        cancel_hint = " اكتب 'إلغاء' للخروج." if lang == "ar" else (" Напишите 'отмена'." if lang == "ru" else " Type 'cancel'.")
        return (whatsapp_service.msg_info(1, 20, lang) + cancel_hint, None)

    if state == SessionState.being_served:
        return (("أنت يتم خدمتك." if lang == "ar" else ("Вас обслуживают." if lang == "ru" else "You are being served.")), None)

    if state == SessionState.done:
        session.state = SessionState.idle
        session.context = {}
        return (_main_menu_text(lang), None)

    return (_main_menu_text(lang), None)


# ---------------------------------------------------------------------------
# Sub-flows
# ---------------------------------------------------------------------------

async def _start_queue(db, tenant, customer, session, lang) -> tuple:
    services = await _get_active_services(db, tenant.id)
    if not services:
        return (_no_services(lang), None)
    if not tenant.is_accepting_queue:
        return (_queue_closed(lang), None)
    session.state = SessionState.selecting_service
    session.context = {**session.context, "service_ids": [str(s.id) for s in services]}
    return (whatsapp_service.msg_welcome(_service_names(services, lang), lang), services)


async def _start_booking(db, tenant, session, lang) -> tuple:
    days = await appointment_service.get_working_days(db, tenant.id, date.today(), count=7)
    if not days:
        return (("لا توجد أيام عمل متاحة." if lang == "ar"
                 else ("Нет рабочих дней." if lang == "ru" else "No working days available.")), None)
    session.state = SessionState.booking_date
    session.context = {**session.context, "booking_days": [str(d) for d in days]}
    return (_format_working_days(days, lang), None)


async def _show_slots(db, tenant, session, lang) -> tuple:
    date_str = session.context.get("booking_date")
    service_id_str = session.context.get("booking_service_id")
    target_date = date.fromisoformat(date_str) if date_str else date.today()
    service_id = uuid.UUID(service_id_str) if service_id_str else None
    slots = await appointment_service.get_available_slots(db, tenant.id, target_date, service_id)
    if not slots:
        days = await appointment_service.get_working_days(db, tenant.id, date.today(), count=7)
        session.state = SessionState.booking_date
        session.context = {**session.context, "booking_days": [str(d) for d in days]}
        return (("لا توجد أوقات متاحة. اختر يوماً آخر:" if lang == "ar"
                 else ("Нет слотов. Выберите другую дату:" if lang == "ru" else "No slots. Choose another date:"))
                + "\n\n" + _format_working_days(days, lang), None)
    # Save slot start times in context for selection by number
    slot_starts = [s.start if hasattr(s, "start") else s["start"] for s in slots]
    session.context = {**session.context, "booking_slots": slot_starts}
    return (_format_slots(slots, lang), None)


def _format_slots_from_context(slot_starts: list, lang: str) -> str:
    lines = []
    for i, start in enumerate(slot_starts):
        dt = datetime.fromisoformat(start).astimezone(KSA_TZ)
        lines.append(f"{i+1}. {dt.strftime('%H:%M')}")
    header = {"ar": "⏰ اختر الوقت:\n\n", "ru": "⏰ Выберите время:\n\n", "en": "⏰ Choose time:\n\n"}.get(lang, "")
    return header + "\n".join(lines)


async def _confirm_booking(db, redis, tenant, customer, session, slot_start_iso, lang) -> tuple:
    service_id_str = session.context.get("booking_service_id")
    service_id = uuid.UUID(service_id_str) if service_id_str else None
    try:
        scheduled_at = datetime.fromisoformat(slot_start_iso)
        await appointment_service.create_appointment(
            db, tenant_id=tenant.id, customer_id=customer.id,
            scheduled_at=scheduled_at, service_id=service_id,
        )
        await db.commit()
        local = scheduled_at.astimezone(KSA_TZ)
        date_str = local.strftime("%-d %B %Y")
        time_str = local.strftime("%H:%M")
        svc = await db.get(Service, service_id) if service_id else None
        service_name = ""
        if svc:
            service_name = svc.name_ar if lang == "ar" else ((svc.name_ru or svc.name_en or svc.name_ar) if lang == "ru" else (svc.name_en or svc.name_ar))
        # Notify manager
        from app.services.manager_notifications import notify_manager
        try:
            await notify_manager(tenant, customer, appt, svc, action="booked")
        except Exception as e:
            logger.warning("Manager notification failed", error=str(e))
        session.state = SessionState.idle
        session.context = {}
        conf = {
            "ar": f"✅ تم تأكيد موعدك!\n📅 {date_str} الساعة {time_str}\n🔧 {service_name}\nسنذكرك قبل ساعة.",
            "ru": f"✅ Запись подтверждена!\n📅 {date_str} в {time_str}\n🔧 {service_name}\nНапомним за час.",
            "en": f"✅ Appointment confirmed!\n📅 {date_str} at {time_str}\n🔧 {service_name}\nWe'll remind you 1h before.",
        }.get(lang, "")
        return (conf, None)
    except ValueError:
        return await _show_slots(db, tenant, session, lang)


async def _show_my_appointments(db, tenant, customer, session, lang) -> tuple:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Appointment).where(
            and_(Appointment.tenant_id == tenant.id,
                 Appointment.customer_id == customer.id,
                 Appointment.status == AppointmentStatus.confirmed,
                 Appointment.scheduled_at >= now)
        ).order_by(Appointment.scheduled_at)
    )
    appointments = list(result.scalars().all())
    session.state = SessionState.my_appointments
    if not appointments:
        msg = {"ar": "📋 ليس لديك مواعيد قادمة.", "ru": "📋 Нет предстоящих записей.", "en": "📋 No upcoming appointments."}.get(lang, "")
        return (msg, None)
    lines = []
    appt_ids = []
    for i, appt in enumerate(appointments):
        local = appt.scheduled_at.astimezone(KSA_TZ)
        lines.append(f"{i+1}. {local.strftime('%-d %b %H:%M')}")
        appt_ids.append(str(appt.id))
    session.context = {**session.context, "appt_ids": appt_ids}
    cancel_hint = {"ar": "\n\nأرسل رقم الموعد لإلغائه:", "ru": "\n\nОтправьте номер для отмены:", "en": "\n\nSend number to cancel:"}.get(lang, "")
    header = {"ar": "📋 مواعيدك القادمة:\n\n", "ru": "📋 Ваши записи:\n\n", "en": "📋 Your appointments:\n\n"}.get(lang, "")
    return (header + "\n".join(lines) + cancel_hint, None)


async def _cancel_appointment(db, tenant, customer, session, appt_id, lang) -> tuple:
    now = datetime.now(timezone.utc)
    appt = await db.get(Appointment, appt_id)
    if not appt or appt.tenant_id != tenant.id:
        return (_main_menu_text(lang), None)
    if (appt.scheduled_at - now).total_seconds() < 7200:
        msg = {"ar": "⚠️ لا يمكن الإلغاء قبل أقل من ساعتين.", "ru": "⚠️ Отмена невозможна менее чем за 2 часа.", "en": "⚠️ Cannot cancel less than 2h before."}.get(lang, "")
        return (msg, None)
    await appointment_service.cancel_appointment(db, tenant.id, appt_id)
    await db.commit()
    # Notify manager
    from app.services.manager_notifications import notify_manager
    svc = await db.get(Service, appt.service_id) if appt.service_id else None
    try:
        await notify_manager(tenant, customer, appt, svc, action="cancelled")
    except Exception as e:
        logger.warning("Manager notification failed", error=str(e))
    session.state = SessionState.idle
    session.context = {}
    msg = {"ar": "✅ تم إلغاء الموعد.", "ru": "✅ Запись отменена.", "en": "✅ Appointment cancelled."}.get(lang, "")
    return (msg, None)


def _no_services(lang):
    return ("عذراً، لا توجد خدمات." if lang == "ar" else ("Нет услуг." if lang == "ru" else "No services."))

def _queue_closed(lang):
    return ("الطابور مغلق." if lang == "ar" else ("Очередь закрыта." if lang == "ru" else "Queue is closed."))


# ---------------------------------------------------------------------------
# Notification senders
# ---------------------------------------------------------------------------

async def send_upcoming_notification(db, redis, entry, tenant) -> None:
    customer = await db.get(Customer, entry.customer_id)
    if not customer or not tenant.d360_api_key:
        return
    lang = customer.preferred_language
    await whatsapp_service.send_message(
        d360_api_key=tenant.d360_api_key, to_phone=customer.phone,
        text=whatsapp_service.msg_upcoming(lang),
    )


async def send_called_notification(db, entry, tenant) -> None:
    customer = await db.get(Customer, entry.customer_id)
    if not customer or not tenant.d360_api_key:
        return
    lang = customer.preferred_language
    await whatsapp_service.send_message(
        d360_api_key=tenant.d360_api_key, to_phone=customer.phone,
        text=whatsapp_service.msg_called(lang),
    )
    from app.models.whatsapp_session import WhatsAppSession as WAS
    result = await db.execute(
        select(WAS).where(and_(WAS.tenant_id == tenant.id, WAS.customer_id == customer.id))
    )
    session = result.scalar_one_or_none()
    if session:
        session.state = SessionState.being_served
        await db.commit()
