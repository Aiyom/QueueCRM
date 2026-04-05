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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _detect_language(text: str, enabled: list[str]) -> str:
    arabic_chars = sum(1 for c in text if "\u0600" <= c <= "\u06ff")
    if arabic_chars > len(text) * 0.2:
        return "ar" if "ar" in enabled else (enabled[0] if enabled else "ar")
    # Rough Cyrillic detection for Russian
    cyrillic_chars = sum(1 for c in text if "\u0400" <= c <= "\u04ff")
    if cyrillic_chars > len(text) * 0.2 and "ru" in enabled:
        return "ru"
    return "en" if "en" in enabled else (enabled[0] if enabled else "en")


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
    """Find customer by phone, create if new, link telegram_chat_id."""
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
    """Process incoming Telegram message and send reply."""
    if not tenant.telegram_bot_token:
        return

    enabled = tenant.enabled_languages or ["ar", "en"]
    text = message_text.strip()
    lang = _detect_language(text, enabled)

    session = await _get_or_create_session(db, tenant.id, chat_id)
    customer = await _get_customer_by_chat_id(db, tenant.id, chat_id)

    reply = await _dispatch(db, redis, tenant, customer, session, chat_id, text, lang, enabled)

    await db.commit()

    if reply:
        await telegram_service.send_message(
            bot_token=tenant.telegram_bot_token,
            chat_id=chat_id,
            text=reply,
        )


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
) -> Optional[str]:
    state = session.state

    # --- WAITING FOR PHONE (new Telegram user) ---
    if state == SessionState.idle and customer is None:
        # Check if text looks like a phone number
        cleaned = text.replace(" ", "").replace("-", "")
        if not cleaned.startswith("+"):
            cleaned = "+" + cleaned
        if PHONE_RE.match(cleaned):
            customer = await _link_or_create_customer(db, tenant.id, cleaned, chat_id, lang)
            session.context = {}
            # Now show services
            services = await _get_active_services(db, tenant.id)
            if not services:
                return (
                    "عذراً، لا توجد خدمات متاحة حالياً."
                    if lang == "ar"
                    else ("Нет доступных услуг." if lang == "ru" else "No services available.")
                )
            session.state = SessionState.selecting_service
            session.context = {"service_ids": [str(s.id) for s in services]}
            names = _service_names(services, lang)
            return telegram_service.msg_phone_saved(lang) + "\n\n" + telegram_service.msg_welcome(names, lang)
        else:
            return telegram_service.msg_ask_phone(lang)

    # --- IDLE (known customer) ---
    if state == SessionState.idle:
        services = await _get_active_services(db, tenant.id)
        if not services:
            return (
                "عذراً، لا توجد خدمات متاحة."
                if lang == "ar"
                else ("Нет доступных услуг." if lang == "ru" else "No services available.")
            )
        if not tenant.is_accepting_queue:
            return (
                "عذراً، الطابور مغلق حالياً."
                if lang == "ar"
                else ("Очередь закрыта." if lang == "ru" else "Queue is closed.")
            )
        session.state = SessionState.selecting_service
        session.context = {"service_ids": [str(s.id) for s in services]}
        names = _service_names(services, lang)
        return telegram_service.msg_welcome(names, lang)

    # --- SELECTING SERVICE ---
    if state == SessionState.selecting_service:
        service_ids = session.context.get("service_ids", [])
        selected_service = None

        if text.isdigit():
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
            return telegram_service.msg_invalid_service(lang)

        if customer is None:
            session.state = SessionState.idle
            return telegram_service.msg_ask_phone(lang)

        existing = await _get_active_queue_entry(db, tenant.id, customer.id)
        if existing:
            return telegram_service.msg_already_in_queue(lang)

        entry = await queue_service.add_to_queue(
            db, redis,
            tenant_id=tenant.id,
            customer_id=customer.id,
            service_id=selected_service.id,
        )
        position = await queue_service.get_queue_position(redis, tenant.id, entry.id)
        eta = (position or 1) * selected_service.avg_duration_minutes

        session.state = SessionState.in_queue
        session.context = {"entry_id": str(entry.id)}
        return telegram_service.msg_queued(position or 1, eta, lang)

    # --- IN QUEUE ---
    if state == SessionState.in_queue:
        if text.lower() in CANCEL_KEYWORDS:
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
            return telegram_service.msg_cancelled(lang)

        entry_id_str = session.context.get("entry_id")
        if entry_id_str:
            position = await queue_service.get_queue_position(
                redis, tenant.id, uuid.UUID(entry_id_str)
            )
            if position:
                return telegram_service.msg_info(position, position * 20, lang)

        return (
            "أنت في الطابور. اكتب 'إلغاء' للخروج."
            if lang == "ar"
            else ("Вы в очереди. Напишите 'отмена' для отмены." if lang == "ru"
                  else "You are in the queue. Type 'cancel' to leave.")
        )

    # --- BEING SERVED ---
    if state == SessionState.being_served:
        return (
            "أنت يتم خدمتك حالياً."
            if lang == "ar"
            else ("Вас обслуживают." if lang == "ru" else "You are currently being served.")
        )

    # --- DONE ---
    if state == SessionState.done:
        session.state = SessionState.idle
        session.context = {}
        services = await _get_active_services(db, tenant.id)
        names = _service_names(services, lang)
        return telegram_service.msg_welcome(names, lang)

    return None


def _service_names(services: list[Service], lang: str) -> list[str]:
    if lang == "ar":
        return [s.name_ar for s in services]
    if lang == "ru":
        return [s.name_en or s.name_ar for s in services]
    return [s.name_en or s.name_ar for s in services]


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
