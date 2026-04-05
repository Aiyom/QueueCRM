"""Telegram bot state machine with live queue + appointment booking."""
import uuid
import re
from datetime import datetime, timezone, timedelta
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
from app.models.telegram_session import TelegramSession
from app.models.whatsapp_session import SessionState
from app.models.appointment import Appointment, AppointmentStatus
from app.services import queue_service, telegram_service, appointment_service

logger = structlog.get_logger(__name__)

SESSION_TTL_HOURS = 24
CANCEL_KEYWORDS = {"إلغاء", "cancel", "الغاء", "يلغي", "إلغى", "отмена", "отменить"}
PHONE_RE = re.compile(r"^\+?\d{9,15}$")
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
KSA_TZ = ZoneInfo("Asia/Riyadh")

_LANG_LABELS = {"ar": "🇸🇦 العربية", "en": "🇬🇧 English", "ru": "🇷🇺 Русский"}


# ---------------------------------------------------------------------------
# Session / customer helpers
# ---------------------------------------------------------------------------

async def _get_or_create_session(db, tenant_id, chat_id) -> TelegramSession:
    result = await db.execute(
        select(TelegramSession).where(
            and_(TelegramSession.tenant_id == tenant_id,
                 TelegramSession.telegram_chat_id == chat_id)
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        session = TelegramSession(
            id=uuid.uuid4(), tenant_id=tenant_id, telegram_chat_id=chat_id,
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


async def _get_customer_by_chat_id(db, tenant_id, chat_id) -> Optional[Customer]:
    result = await db.execute(
        select(Customer).where(
            and_(Customer.tenant_id == tenant_id, Customer.telegram_chat_id == chat_id)
        )
    )
    return result.scalar_one_or_none()


async def _link_or_create_customer(db, tenant_id, phone, chat_id, lang) -> Customer:
    result = await db.execute(
        select(Customer).where(and_(Customer.tenant_id == tenant_id, Customer.phone == phone))
    )
    customer = result.scalar_one_or_none()
    if not customer:
        customer = Customer(
            id=uuid.uuid4(), tenant_id=tenant_id, phone=phone,
            preferred_language=lang, telegram_chat_id=chat_id,
        )
        db.add(customer)
        await db.flush()
    else:
        customer.telegram_chat_id = chat_id
        customer.preferred_language = lang
    return customer


async def _get_active_services(db, tenant_id) -> list[Service]:
    result = await db.execute(
        select(Service)
        .where(and_(Service.tenant_id == tenant_id, Service.is_active == True))  # noqa: E712
        .order_by(Service.sort_order)
    )
    return list(result.scalars().all())


async def _get_active_queue_entry(db, tenant_id, customer_id) -> Optional[QueueEntry]:
    result = await db.execute(
        select(QueueEntry).where(
            and_(QueueEntry.tenant_id == tenant_id,
                 QueueEntry.customer_id == customer_id,
                 QueueEntry.status.in_([QueueStatus.waiting, QueueStatus.called]))
        )
    )
    return result.scalar_one_or_none()


def _service_names(services, lang) -> list[str]:
    if lang == "ar":
        return [s.name_ar for s in services]
    if lang == "ru":
        return [s.name_ru or s.name_en or s.name_ar for s in services]
    return [s.name_en or s.name_ar for s in services]


def _services_keyboard(services, lang) -> list[list[dict]]:
    names = _service_names(services, lang)
    return [[{"text": name, "callback_data": str(svc.id)}]
            for svc, name in zip(services, names)]


def _cancel_keyboard(lang) -> list[list[dict]]:
    label = "إلغاء ❌" if lang == "ar" else ("Отмена ❌" if lang == "ru" else "Cancel ❌")
    return [[{"text": label, "callback_data": "cancel"}]]


def _lang_keyboard(enabled) -> list[list[dict]]:
    return [[{"text": _LANG_LABELS[l], "callback_data": f"lang:{l}"}]
            for l in enabled if l in _LANG_LABELS]


def _dates_keyboard(dates: list, lang: str) -> list[list[dict]]:
    """Keyboard with working day buttons."""
    buttons = []
    for d in dates:
        dt = datetime.strptime(d, "%Y-%m-%d") if isinstance(d, str) else d
        label = dt.strftime("%-d %b")  # e.g. "10 Apr"
        buttons.append([{"text": label, "callback_data": f"date:{d}"}])
    back_label = "⬅️ رجوع" if lang == "ar" else ("⬅️ Назад" if lang == "ru" else "⬅️ Back")
    buttons.append([{"text": back_label, "callback_data": "menu:back"}])
    return buttons


def _slots_keyboard(slots, lang: str) -> list[list[dict]]:
    """Keyboard with time slot buttons (2 per row)."""
    buttons = []
    row = []
    for slot in slots:
        dt = datetime.fromisoformat(slot.start) if hasattr(slot, "start") else datetime.fromisoformat(slot["start"])
        local = dt.astimezone(KSA_TZ)
        label = local.strftime("%H:%M")
        row.append({"text": label, "callback_data": f"slot:{slot.start if hasattr(slot, 'start') else slot['start']}"})
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    back_label = "⬅️ رجوع" if lang == "ar" else ("⬅️ Назад" if lang == "ru" else "⬅️ Back")
    buttons.append([{"text": back_label, "callback_data": "book:back_date"}])
    return buttons


def _my_appointments_keyboard(appointments: list, lang: str) -> list[list[dict]]:
    """Show list of upcoming appointments with cancel buttons."""
    buttons = []
    for appt in appointments:
        dt = datetime.fromisoformat(appt.scheduled_at.isoformat()).astimezone(KSA_TZ)
        label = dt.strftime("%-d %b %H:%M")
        buttons.append([{"text": f"❌ {label}", "callback_data": f"cancel_appt:{appt.id}"}])
    back_label = "⬅️ رجوع" if lang == "ar" else ("⬅️ Назад" if lang == "ru" else "⬅️ Back")
    buttons.append([{"text": back_label, "callback_data": "menu:back"}])
    return buttons


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def handle_message(
    db: AsyncSession, redis: Redis, *, tenant: Tenant, chat_id: str, message_text: str
) -> None:
    if not tenant.telegram_bot_token:
        return

    enabled = tenant.enabled_languages or ["ar", "en"]
    text = message_text.strip()
    session = await _get_or_create_session(db, tenant.id, chat_id)

    if text == "/start":
        session.state = SessionState.idle
        session.context = {}

    saved_lang = session.context.get("language")
    lang = saved_lang if (saved_lang and saved_lang in enabled) else _detect_language(text, enabled)

    customer = await _get_customer_by_chat_id(db, tenant.id, chat_id)

    reply_text, reply_keyboard = await _dispatch(
        db, redis, tenant, customer, session, chat_id, text, lang, enabled
    )

    await db.commit()

    token = tenant.telegram_bot_token
    if reply_text and reply_keyboard is not None:
        await telegram_service.send_with_keyboard(
            bot_token=token, chat_id=chat_id, text=reply_text, keyboard=reply_keyboard
        )
    elif reply_text:
        await telegram_service.send_message(bot_token=token, chat_id=chat_id, text=reply_text)


def _detect_language(text: str, enabled: list[str]) -> str:
    enabled = enabled or ["ar", "en"]
    arabic = sum(1 for c in text if "\u0600" <= c <= "\u06ff")
    cyrillic = sum(1 for c in text if "\u0400" <= c <= "\u04ff")
    if arabic > len(text) * 0.2 and "ar" in enabled:
        return "ar"
    if cyrillic > len(text) * 0.2 and "ru" in enabled:
        return "ru"
    return "en" if "en" in enabled else enabled[0]


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

async def _dispatch(
    db, redis, tenant, customer, session, chat_id, text, lang, enabled
) -> tuple[Optional[str], Optional[list]]:
    state = session.state

    # --- LANGUAGE SELECTION ---
    if text.startswith("lang:"):
        chosen = text.split(":")[1]
        if chosen in enabled:
            lang = chosen
            session.context = {**session.context, "language": lang}
            if customer:
                customer.preferred_language = lang
        if customer is None:
            return (telegram_service.msg_ask_phone(lang), None)
        return (telegram_service.msg_main_menu(lang), telegram_service.main_menu_keyboard(lang))

    # --- LANGUAGE PICKER if not yet selected ---
    if state == SessionState.idle and "language" not in session.context:
        if len(enabled) == 1:
            session.context = {"language": enabled[0]}
            lang = enabled[0]
        else:
            return (telegram_service.msg_select_language(), _lang_keyboard(enabled))

    # --- PHONE (new user) ---
    if state == SessionState.idle and customer is None:
        cleaned = text.replace(" ", "").replace("-", "")
        if not cleaned.startswith("+"):
            cleaned = "+" + cleaned
        if PHONE_RE.match(cleaned):
            customer = await _link_or_create_customer(db, tenant.id, cleaned, chat_id, lang)
            session.context = {**session.context}
            await telegram_service.send_message(
                bot_token=tenant.telegram_bot_token, chat_id=chat_id,
                text=telegram_service.msg_phone_saved(lang)
            )
            return (telegram_service.msg_main_menu(lang), telegram_service.main_menu_keyboard(lang))
        return (telegram_service.msg_ask_phone(lang), None)

    # --- MAIN MENU callbacks ---
    if text == "menu:queue" or (state == SessionState.idle and text not in ("menu:book", "menu:my_appointments", "menu:back")):
        # Show live queue flow
        if text == "menu:queue" or state == SessionState.idle:
            services = await _get_active_services(db, tenant.id)
            if not services:
                return (_no_services(lang), None)
            if not tenant.is_accepting_queue:
                return (_queue_closed(lang), None)
            session.state = SessionState.selecting_service
            session.context = {**session.context, "service_ids": [str(s.id) for s in services]}
            return (
                telegram_service.msg_welcome(_service_names(services, lang), lang),
                _services_keyboard(services, lang)
            )

    if text == "menu:back":
        session.state = SessionState.idle
        session.context = {k: v for k, v in session.context.items() if k in ("language",)}
        return (telegram_service.msg_main_menu(lang), telegram_service.main_menu_keyboard(lang))

    if text == "menu:book":
        return await _start_booking(db, tenant, session, lang)

    if text == "menu:my_appointments":
        return await _show_my_appointments(db, tenant, customer, session, lang)

    # --- BOOKING FLOW ---
    if state == SessionState.booking_date:
        if text.startswith("date:"):
            chosen_date = text.split(":", 1)[1]
            session.context = {**session.context, "booking_date": chosen_date}
            # Go to service selection
            services = await _get_active_services(db, tenant.id)
            if not services:
                return (_no_services(lang), None)
            session.state = SessionState.booking_service
            session.context = {**session.context, "service_ids": [str(s.id) for s in services]}
            return (telegram_service.msg_pick_service(lang), _services_keyboard(services, lang))
        if text == "menu:back":
            session.state = SessionState.idle
            return (telegram_service.msg_main_menu(lang), telegram_service.main_menu_keyboard(lang))

    if state == SessionState.booking_service:
        if UUID_RE.match(text):
            service = await db.get(Service, uuid.UUID(text))
            if service:
                session.context = {**session.context, "booking_service_id": str(service.id)}
                session.state = SessionState.booking_time
                return await _show_slots(db, tenant, session, lang)
        if text == "menu:back":
            return await _start_booking(db, tenant, session, lang)

    if state == SessionState.booking_time:
        if text.startswith("slot:"):
            slot_start = text.split(":", 1)[1]
            return await _confirm_booking(db, redis, tenant, customer, session, chat_id, slot_start, lang)
        if text == "book:back_date":
            return await _start_booking(db, tenant, session, lang)

    # --- MY APPOINTMENTS ---
    if state == SessionState.my_appointments:
        if text.startswith("cancel_appt:"):
            appt_id = uuid.UUID(text.split(":", 1)[1])
            return await _cancel_appointment(db, tenant, customer, session, appt_id, lang)
        if text == "menu:back":
            session.state = SessionState.idle
            return (telegram_service.msg_main_menu(lang), telegram_service.main_menu_keyboard(lang))

    # --- LIVE QUEUE STATES ---
    if state == SessionState.selecting_service:
        service_ids = session.context.get("service_ids", [])
        selected_service = None
        if UUID_RE.match(text):
            selected_service = await db.get(Service, uuid.UUID(text))
        elif text.isdigit():
            idx = int(text) - 1
            if 0 <= idx < len(service_ids):
                selected_service = await db.get(Service, uuid.UUID(service_ids[idx]))

        if not selected_service:
            return (telegram_service.msg_invalid_service(lang), None)
        if customer is None:
            session.state = SessionState.idle
            return (telegram_service.msg_ask_phone(lang), None)

        existing = await _get_active_queue_entry(db, tenant.id, customer.id)
        if existing:
            return (telegram_service.msg_already_in_queue(lang), None)

        entry = await queue_service.add_to_queue(
            db, redis, tenant_id=tenant.id,
            customer_id=customer.id, service_id=selected_service.id,
        )
        position = await queue_service.get_queue_position(redis, tenant.id, entry.id)
        eta = (position or 1) * selected_service.avg_duration_minutes
        session.state = SessionState.in_queue
        session.context = {**session.context, "entry_id": str(entry.id)}
        return (telegram_service.msg_queued(position or 1, eta, lang), _cancel_keyboard(lang))

    if state == SessionState.in_queue:
        if text.lower() in CANCEL_KEYWORDS or text == "cancel":
            entry_id_str = session.context.get("entry_id")
            if entry_id_str:
                try:
                    await queue_service.cancel_entry(db, redis, tenant.id, uuid.UUID(entry_id_str))
                except ValueError:
                    pass
            session.state = SessionState.idle
            session.context = {k: v for k, v in session.context.items() if k in ("language",)}
            return (telegram_service.msg_cancelled(lang), telegram_service.main_menu_keyboard(lang))

        entry_id_str = session.context.get("entry_id")
        if entry_id_str:
            position = await queue_service.get_queue_position(redis, tenant.id, uuid.UUID(entry_id_str))
            if position:
                return (telegram_service.msg_info(position, position * 20, lang), _cancel_keyboard(lang))
        return (_queue_in_queue_text(lang), _cancel_keyboard(lang))

    if state == SessionState.being_served:
        return (_being_served(lang), None)

    if state == SessionState.done:
        session.state = SessionState.idle
        session.context = {k: v for k, v in session.context.items() if k in ("language",)}
        return (telegram_service.msg_main_menu(lang), telegram_service.main_menu_keyboard(lang))

    # Fallback — show main menu
    return (telegram_service.msg_main_menu(lang), telegram_service.main_menu_keyboard(lang))


# ---------------------------------------------------------------------------
# Booking helpers
# ---------------------------------------------------------------------------

async def _start_booking(db, tenant, session, lang) -> tuple:
    """Show working day picker."""
    from datetime import date
    days = await appointment_service.get_working_days(db, tenant.id, date.today(), count=7)
    if not days:
        return (telegram_service.msg_no_working_days(lang), None)
    session.state = SessionState.booking_date
    session.context = {**session.context}
    return (telegram_service.msg_pick_date(lang), _dates_keyboard(days, lang))


async def _show_slots(db, tenant, session, lang) -> tuple:
    """Show available time slots for chosen date + service."""
    from datetime import date
    date_str = session.context.get("booking_date")
    service_id_str = session.context.get("booking_service_id")
    if not date_str:
        return await _start_booking(db, tenant, session, lang)

    target_date = date.fromisoformat(date_str)
    service_id = uuid.UUID(service_id_str) if service_id_str else None
    slots = await appointment_service.get_available_slots(db, tenant.id, target_date, service_id)
    if not slots:
        # No slots — go back to date picker
        days = await appointment_service.get_working_days(db, tenant.id, date.today(), count=7)
        session.state = SessionState.booking_date
        return (telegram_service.msg_no_slots(lang), _dates_keyboard(days, lang))

    return (telegram_service.msg_pick_time(lang), _slots_keyboard(slots, lang))


async def _confirm_booking(db, redis, tenant, customer, session, chat_id, slot_start_iso, lang) -> tuple:
    """Create appointment and send confirmation."""
    if customer is None:
        session.state = SessionState.idle
        return (telegram_service.msg_ask_phone(lang), None)

    service_id_str = session.context.get("booking_service_id")
    service_id = uuid.UUID(service_id_str) if service_id_str else None

    try:
        scheduled_at = datetime.fromisoformat(slot_start_iso)
        appt = await appointment_service.create_appointment(
            db, tenant_id=tenant.id, customer_id=customer.id,
            scheduled_at=scheduled_at, service_id=service_id,
        )
        await db.commit()

        # Notify manager via bot if they have Telegram — skip for now, just log
        logger.info("Appointment booked via bot", appointment_id=str(appt.id))

        local = scheduled_at.astimezone(KSA_TZ)
        date_str = local.strftime("%-d %B %Y")
        time_str = local.strftime("%H:%M")

        service_name = ""
        if service_id:
            svc = await db.get(Service, service_id)
            if svc:
                service_name = svc.name_ar if lang == "ar" else (
                    (svc.name_ru or svc.name_en or svc.name_ar) if lang == "ru"
                    else (svc.name_en or svc.name_ar)
                )

        session.state = SessionState.idle
        session.context = {k: v for k, v in session.context.items() if k in ("language",)}

        conf_text = telegram_service.msg_booking_confirmed(date_str, time_str, service_name, lang)
        return (conf_text, telegram_service.main_menu_keyboard(lang))

    except ValueError as e:
        # Slot taken — show updated slots
        logger.warning("Booking failed", error=str(e))
        return await _show_slots(db, tenant, session, lang)


async def _show_my_appointments(db, tenant, customer, session, lang) -> tuple:
    """Show upcoming confirmed appointments with cancel buttons."""
    if customer is None:
        session.state = SessionState.idle
        return (telegram_service.msg_ask_phone(lang), None)

    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Appointment).where(
            and_(
                Appointment.tenant_id == tenant.id,
                Appointment.customer_id == customer.id,
                Appointment.status == AppointmentStatus.confirmed,
                Appointment.scheduled_at >= now,
            )
        ).order_by(Appointment.scheduled_at)
    )
    appointments = list(result.scalars().all())

    session.state = SessionState.my_appointments

    if not appointments:
        return (telegram_service.msg_my_appointments_empty(lang), telegram_service.main_menu_keyboard(lang))

    # Build text list + keyboard
    lines = []
    for appt in appointments:
        local = appt.scheduled_at.astimezone(KSA_TZ)
        lines.append(f"📅 {local.strftime('%-d %b %H:%M')}")
    text = "\n".join(lines)
    cancel_hint = {
        "ar": "\n\nاضغط على الموعد لإلغائه:",
        "ru": "\n\nНажмите на запись для отмены:",
        "en": "\n\nTap an appointment to cancel:",
    }.get(lang, "")
    return (text + cancel_hint, _my_appointments_keyboard(appointments, lang))


async def _cancel_appointment(db, tenant, customer, session, appt_id, lang) -> tuple:
    """Cancel appointment if > 2h before."""
    now = datetime.now(timezone.utc)
    appt = await db.get(Appointment, appt_id)

    if not appt or appt.tenant_id != tenant.id or (customer and appt.customer_id != customer.id):
        return (telegram_service.msg_my_appointments_empty(lang), telegram_service.main_menu_keyboard(lang))

    if (appt.scheduled_at - now).total_seconds() < 7200:
        return (telegram_service.msg_cancel_too_late(lang), None)

    await appointment_service.cancel_appointment(db, tenant.id, appt_id)
    await db.commit()

    session.state = SessionState.idle
    session.context = {k: v for k, v in session.context.items() if k in ("language",)}
    return (telegram_service.msg_appointment_cancelled(lang), telegram_service.main_menu_keyboard(lang))


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def _no_services(lang):
    return ("عذراً، لا توجد خدمات متاحة." if lang == "ar"
            else ("Нет доступных услуг." if lang == "ru" else "No services available."))

def _queue_closed(lang):
    return ("عذراً، الطابور مغلق حالياً." if lang == "ar"
            else ("Очередь закрыта." if lang == "ru" else "Queue is closed."))

def _queue_in_queue_text(lang):
    return ("أنت في الطابور. اضغط إلغاء للخروج." if lang == "ar"
            else ("Вы в очереди. Нажмите Отмена." if lang == "ru"
                  else "You are in the queue. Press Cancel to leave."))

def _being_served(lang):
    return ("أنت يتم خدمتك حالياً." if lang == "ar"
            else ("Вас обслуживают." if lang == "ru" else "You are currently being served."))


# ---------------------------------------------------------------------------
# Notification senders (called from queue_service)
# ---------------------------------------------------------------------------

async def send_upcoming_notification(db, entry, tenant) -> None:
    customer = await db.get(Customer, entry.customer_id)
    if not customer or not customer.telegram_chat_id or not tenant.telegram_bot_token:
        return
    lang = customer.preferred_language
    await telegram_service.send_message(
        bot_token=tenant.telegram_bot_token, chat_id=customer.telegram_chat_id,
        text=telegram_service.msg_upcoming(lang),
    )


async def send_called_notification(db, entry, tenant) -> None:
    customer = await db.get(Customer, entry.customer_id)
    if not customer or not customer.telegram_chat_id or not tenant.telegram_bot_token:
        return
    lang = customer.preferred_language
    await telegram_service.send_message(
        bot_token=tenant.telegram_bot_token, chat_id=customer.telegram_chat_id,
        text=telegram_service.msg_called(lang),
    )
    result = await db.execute(
        select(TelegramSession).where(
            and_(TelegramSession.tenant_id == tenant.id,
                 TelegramSession.telegram_chat_id == customer.telegram_chat_id)
        )
    )
    session = result.scalar_one_or_none()
    if session:
        session.state = SessionState.being_served
        await db.commit()
