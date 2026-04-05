"""Telegram bot state machine — mirrors bot_service.py logic for WhatsApp."""
import uuid
import re
from datetime import datetime, timezone, timedelta
from typing import Optional

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
from app.services import queue_service, telegram_service

logger = structlog.get_logger(__name__)

SESSION_TTL_HOURS = 24
CANCEL_KEYWORDS = {"إلغاء", "cancel", "الغاء", "يلغي", "إلغى", "отмена", "отменить"}
PHONE_RE = re.compile(r"^\+?\d{9,15}$")
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _detect_language(text: str, enabled: list[str]) -> str:
    enabled = enabled or ["ar", "en"]
    arabic_chars = sum(1 for c in text if "\u0600" <= c <= "\u06ff")
    cyrillic_chars = sum(1 for c in text if "\u0400" <= c <= "\u04ff")

    if arabic_chars > len(text) * 0.2 and "ar" in enabled:
        return "ar"
    if cyrillic_chars > len(text) * 0.2 and "ru" in enabled:
        return "ru"
    if "en" in enabled:
        return "en"
    return enabled[0]


async def _get_or_create_session(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    chat_id: str,
) -> TelegramSession:
    result = await db.execute(
        select(TelegramSession).where(
            and_(
                TelegramSession.tenant_id == tenant_id,
                TelegramSession.telegram_chat_id == chat_id,
            )
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        session = TelegramSession(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            telegram_chat_id=chat_id,
            state=SessionState.idle,
            context={},
            expires_at=datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS),
        )
        db.add(session)
    else:
        if session.expires_at < datetime.now(timezone.utc):
            session.state = SessionState.idle
            session.context = {}
        session.expires_at = datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)
    return session


async def _get_customer_by_chat_id(
    db: AsyncSession, tenant_id: uuid.UUID, chat_id: str
) -> Optional[Customer]:
    result = await db.execute(
        select(Customer).where(
            and_(
                Customer.tenant_id == tenant_id,
                Customer.telegram_chat_id == chat_id,
            )
        )
    )
    return result.scalar_one_or_none()


async def _link_or_create_customer(
    db: AsyncSession, tenant_id: uuid.UUID, phone: str, chat_id: str, lang: str
) -> Customer:
    result = await db.execute(
        select(Customer).where(
            and_(Customer.tenant_id == tenant_id, Customer.phone == phone)
        )
    )
    customer = result.scalar_one_or_none()
    if not customer:
        customer = Customer(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            phone=phone,
            preferred_language=lang,
            telegram_chat_id=chat_id,
        )
        db.add(customer)
        await db.flush()
    else:
        customer.telegram_chat_id = chat_id
        customer.preferred_language = lang
    return customer


async def _get_active_services(db: AsyncSession, tenant_id: uuid.UUID) -> list[Service]:
    result = await db.execute(
        select(Service)
        .where(and_(Service.tenant_id == tenant_id, Service.is_active == True))  # noqa: E712
        .order_by(Service.sort_order)
    )
    return list(result.scalars().all())


async def _get_active_queue_entry(
    db: AsyncSession, tenant_id: uuid.UUID, customer_id: uuid.UUID
) -> Optional[QueueEntry]:
    result = await db.execute(
        select(QueueEntry).where(
            and_(
                QueueEntry.tenant_id == tenant_id,
                QueueEntry.customer_id == customer_id,
                QueueEntry.status.in_([QueueStatus.waiting, QueueStatus.called]),
            )
        )
    )
    return result.scalar_one_or_none()


def _service_names(services: list[Service], lang: str) -> list[str]:
    if lang == "ar":
        return [s.name_ar for s in services]
    if lang == "ru":
        return [s.name_ru or s.name_en or s.name_ar for s in services]
    return [s.name_en or s.name_ar for s in services]


def _services_keyboard(services: list[Service], lang: str) -> list[list[dict]]:
    """Build inline keyboard — one button per service row."""
    names = _service_names(services, lang)
    return [[{"text": name, "callback_data": str(svc.id)}]
            for svc, name in zip(services, names)]


def _cancel_keyboard(lang: str) -> list[list[dict]]:
    label = "إلغاء ❌" if lang == "ar" else ("Отмена ❌" if lang == "ru" else "Cancel ❌")
    return [[{"text": label, "callback_data": "cancel"}]]


_LANG_LABELS = {"ar": "🇸🇦 العربية", "en": "🇬🇧 English", "ru": "🇷🇺 Русский"}


def _lang_keyboard(enabled: list[str]) -> list[list[dict]]:
    """Language selection buttons — one per row, only enabled languages."""
    return [
        [{"text": _LANG_LABELS[l], "callback_data": f"lang:{l}"}]
        for l in enabled if l in _LANG_LABELS
    ]


# ---------------------------------------------------------------------------
# Main handler
# ---------------------------------------------------------------------------


async def handle_message(
    db: AsyncSession,
    redis: Redis,
    *,
    tenant: Tenant,
    chat_id: str,
    message_text: str,
) -> None:
    """Process incoming Telegram message or callback and send reply."""
    if not tenant.telegram_bot_token:
        return

    enabled = tenant.enabled_languages or ["ar", "en"]
    text = message_text.strip()

    session = await _get_or_create_session(db, tenant.id, chat_id)

    # /start resets session and triggers language picker
    if text == "/start":
        session.state = SessionState.idle
        session.context = {}

    # Language stored in session takes priority over auto-detect
    saved_lang = session.context.get("language")
    if saved_lang and saved_lang in enabled:
        lang = saved_lang
    else:
        lang = _detect_language(text, enabled)

    customer = await _get_customer_by_chat_id(db, tenant.id, chat_id)

    reply_text, reply_services, reply_keyboard = await _dispatch(
        db, redis, tenant, customer, session, chat_id, text, lang, enabled
    )

    await db.commit()

    token = tenant.telegram_bot_token

    if reply_services is not None:
        # Show service selection with inline keyboard
        keyboard = _services_keyboard(reply_services, lang)
        await telegram_service.send_with_keyboard(
            bot_token=token,
            chat_id=chat_id,
            text=reply_text or telegram_service.msg_welcome(
                _service_names(reply_services, lang), lang
            ),
            keyboard=keyboard,
        )
    elif reply_text and reply_keyboard is not None:
        await telegram_service.send_with_keyboard(
            bot_token=token, chat_id=chat_id, text=reply_text, keyboard=reply_keyboard
        )
    elif reply_text:
        await telegram_service.send_message(
            bot_token=token, chat_id=chat_id, text=reply_text
        )


# Return type: (text | None, services_for_keyboard | None, extra_keyboard | None)
async def _dispatch(
    db: AsyncSession,
    redis: Redis,
    tenant: Tenant,
    customer: Optional[Customer],
    session: TelegramSession,
    chat_id: str,
    text: str,
    lang: str,
    enabled: list[str],
) -> tuple[Optional[str], Optional[list[Service]], Optional[list[list[dict]]]]:
    state = session.state

    # --- LANGUAGE SELECTION callback (lang:ar / lang:en / lang:ru) ---
    if text.startswith("lang:"):
        chosen = text.split(":")[1]
        if chosen in enabled:
            lang = chosen
            session.context = {**session.context, "language": lang}
            if customer:
                customer.preferred_language = lang
        # After language chosen → proceed to phone ask or services
        if customer is None:
            return (telegram_service.msg_ask_phone(lang), None, None)
        services = await _get_active_services(db, tenant.id)
        if not services or not tenant.is_accepting_queue:
            msg = ("عذراً، الطابور مغلق حالياً." if lang == "ar"
                   else ("Очередь закрыта." if lang == "ru" else "Queue is closed."))
            return (msg, None, None)
        session.state = SessionState.selecting_service
        session.context = {**session.context, "service_ids": [str(s.id) for s in services]}
        return (telegram_service.msg_welcome(_service_names(services, lang), lang), services, None)

    # --- SHOW LANGUAGE PICKER if language not yet selected ---
    if state == SessionState.idle and "language" not in session.context:
        if len(enabled) == 1:
            # Only one language — skip picker, save it automatically
            session.context = {"language": enabled[0]}
            lang = enabled[0]
        else:
            return (
                telegram_service.msg_select_language(),
                None,
                _lang_keyboard(enabled),
            )

    # --- WAITING FOR PHONE (new Telegram user) ---
    if state == SessionState.idle and customer is None:
        cleaned = text.replace(" ", "").replace("-", "")
        if not cleaned.startswith("+"):
            cleaned = "+" + cleaned
        if PHONE_RE.match(cleaned):
            customer = await _link_or_create_customer(db, tenant.id, cleaned, chat_id, lang)
            session.context = {}
            services = await _get_active_services(db, tenant.id)
            if not services:
                return (
                    "عذراً، لا توجد خدمات متاحة حالياً." if lang == "ar"
                    else ("Нет доступных услуг." if lang == "ru" else "No services available."),
                    None, None
                )
            session.state = SessionState.selecting_service
            session.context = {**session.context, "service_ids": [str(s.id) for s in services]}
            header = telegram_service.msg_phone_saved(lang)
            welcome = telegram_service.msg_welcome(_service_names(services, lang), lang)
            # Send phone-saved text first, then service keyboard
            await telegram_service.send_message(
                bot_token=tenant.telegram_bot_token, chat_id=chat_id, text=header
            )
            return (welcome, services, None)
        else:
            return (telegram_service.msg_ask_phone(lang), None, None)

    # --- IDLE (known customer) ---
    if state == SessionState.idle:
        services = await _get_active_services(db, tenant.id)
        if not services:
            return (
                "عذراً، لا توجد خدمات متاحة." if lang == "ar"
                else ("Нет доступных услуг." if lang == "ru" else "No services available."),
                None, None
            )
        if not tenant.is_accepting_queue:
            return (
                "عذراً، الطابور مغلق حالياً." if lang == "ar"
                else ("Очередь закрыта." if lang == "ru" else "Queue is closed."),
                None, None
            )
        session.state = SessionState.selecting_service
        session.context = {**session.context, "service_ids": [str(s.id) for s in services]}
        return (telegram_service.msg_welcome(_service_names(services, lang), lang), services, None)

    # --- SELECTING SERVICE ---
    if state == SessionState.selecting_service:
        service_ids = session.context.get("service_ids", [])
        selected_service = None

        # Inline keyboard sends UUID as callback_data
        if UUID_RE.match(text):
            try:
                selected_service = await db.get(Service, uuid.UUID(text))
            except Exception:
                pass
        elif text.isdigit():
            idx = int(text) - 1
            if 0 <= idx < len(service_ids):
                selected_service = await db.get(Service, uuid.UUID(service_ids[idx]))
        else:
            services = await _get_active_services(db, tenant.id)
            for svc in services:
                if text.lower() in svc.name_ar.lower() or text.lower() in (svc.name_en or "").lower():
                    selected_service = svc
                    break

        if not selected_service:
            return (telegram_service.msg_invalid_service(lang), None, None)

        if customer is None:
            session.state = SessionState.idle
            return (telegram_service.msg_ask_phone(lang), None, None)

        existing = await _get_active_queue_entry(db, tenant.id, customer.id)
        if existing:
            return (telegram_service.msg_already_in_queue(lang), None, None)

        entry = await queue_service.add_to_queue(
            db, redis,
            tenant_id=tenant.id,
            customer_id=customer.id,
            service_id=selected_service.id,
        )
        position = await queue_service.get_queue_position(redis, tenant.id, entry.id)
        eta = (position or 1) * selected_service.avg_duration_minutes

        session.state = SessionState.in_queue
        session.context = {**session.context, "entry_id": str(entry.id)}
        queued_text = telegram_service.msg_queued(position or 1, eta, lang)
        return (queued_text, None, _cancel_keyboard(lang))

    # --- IN QUEUE ---
    if state == SessionState.in_queue:
        if text.lower() in CANCEL_KEYWORDS or text == "cancel":
            entry_id_str = session.context.get("entry_id")
            if entry_id_str:
                try:
                    await queue_service.cancel_entry(
                        db, redis, tenant.id, uuid.UUID(entry_id_str)
                    )
                except ValueError:
                    pass
            session.state = SessionState.idle
            session.context = {}
            return (telegram_service.msg_cancelled(lang), None, None)

        entry_id_str = session.context.get("entry_id")
        if entry_id_str:
            position = await queue_service.get_queue_position(
                redis, tenant.id, uuid.UUID(entry_id_str)
            )
            if position:
                return (
                    telegram_service.msg_info(position, position * 20, lang),
                    None,
                    _cancel_keyboard(lang),
                )

        return (
            "أنت في الطابور. اضغط إلغاء للخروج." if lang == "ar"
            else ("Вы в очереди. Нажмите Отмена." if lang == "ru"
                  else "You are in the queue. Press Cancel to leave."),
            None,
            _cancel_keyboard(lang),
        )

    # --- BEING SERVED ---
    if state == SessionState.being_served:
        return (
            "أنت يتم خدمتك حالياً." if lang == "ar"
            else ("Вас обслуживают." if lang == "ru" else "You are currently being served."),
            None, None
        )

    # --- DONE ---
    if state == SessionState.done:
        session.state = SessionState.idle
        session.context = {}
        services = await _get_active_services(db, tenant.id)
        return (telegram_service.msg_welcome(_service_names(services, lang), lang), services, None)

    return (None, None, None)


# ---------------------------------------------------------------------------
# Notification senders
# ---------------------------------------------------------------------------


async def send_upcoming_notification(
    db: AsyncSession,
    entry: QueueEntry,
    tenant: Tenant,
) -> None:
    customer = await db.get(Customer, entry.customer_id)
    if not customer or not customer.telegram_chat_id or not tenant.telegram_bot_token:
        return
    lang = customer.preferred_language
    await telegram_service.send_message(
        bot_token=tenant.telegram_bot_token,
        chat_id=customer.telegram_chat_id,
        text=telegram_service.msg_upcoming(lang),
    )


async def send_called_notification(
    db: AsyncSession,
    entry: QueueEntry,
    tenant: Tenant,
) -> None:
    customer = await db.get(Customer, entry.customer_id)
    if not customer or not customer.telegram_chat_id or not tenant.telegram_bot_token:
        return
    lang = customer.preferred_language
    await telegram_service.send_message(
        bot_token=tenant.telegram_bot_token,
        chat_id=customer.telegram_chat_id,
        text=telegram_service.msg_called(lang),
    )

    result = await db.execute(
        select(TelegramSession).where(
            and_(
                TelegramSession.tenant_id == tenant.id,
                TelegramSession.telegram_chat_id == customer.telegram_chat_id,
            )
        )
    )
    session = result.scalar_one_or_none()
    if session:
        session.state = SessionState.being_served
        await db.commit()
