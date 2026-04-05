"""WhatsApp bot state machine."""
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
from app.models.whatsapp_session import WhatsAppSession, SessionState
from app.services import queue_service, whatsapp_service

logger = structlog.get_logger(__name__)

SESSION_TTL_HOURS = 24
CANCEL_KEYWORDS = {"إلغاء", "cancel", "الغاء", "يلغي", "إلغى", "отмена", "отменить"}
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------


async def _get_or_create_session(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    customer_id: uuid.UUID,
) -> WhatsAppSession:
    result = await db.execute(
        select(WhatsAppSession).where(
            and_(
                WhatsAppSession.tenant_id == tenant_id,
                WhatsAppSession.customer_id == customer_id,
            )
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        session = WhatsAppSession(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            customer_id=customer_id,
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


async def _get_or_create_customer(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    phone: str,
    lang: str,
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
        )
        db.add(customer)
        await db.flush()
    else:
        customer.preferred_language = lang
    return customer


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


async def _get_active_services(
    db: AsyncSession, tenant_id: uuid.UUID
) -> list[Service]:
    result = await db.execute(
        select(Service)
        .where(and_(Service.tenant_id == tenant_id, Service.is_active == True))  # noqa: E712
        .order_by(Service.sort_order)
    )
    return list(result.scalars().all())


def _service_names(services: list[Service], lang: str) -> list[str]:
    if lang == "ar":
        return [s.name_ar for s in services]
    if lang == "ru":
        return [s.name_ru or s.name_en or s.name_ar for s in services]
    return [s.name_en or s.name_ar for s in services]


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
    phone: str,
    message_text: str,
) -> None:
    """Process incoming WhatsApp message and send reply."""
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
        # Send interactive list for service selection
        await whatsapp_service.send_interactive_list(
            d360_api_key=d360_api_key,
            to_phone=phone,
            body_text=reply or whatsapp_service.msg_welcome(
                _service_names(services_for_list, lang), lang
            ),
            services=services_for_list,
            lang=lang,
        )
    elif reply:
        await whatsapp_service.send_message(
            d360_api_key=d360_api_key,
            to_phone=phone,
            text=reply,
        )


async def _dispatch(
    db: AsyncSession,
    redis: Redis,
    tenant: Tenant,
    customer: Customer,
    session: WhatsAppSession,
    text: str,
    lang: str,
) -> tuple[Optional[str], Optional[list]]:
    """Returns (reply_text, services_for_interactive_list).

    When services is not None, caller sends an interactive list message.
    """
    state = session.state

    # --- IDLE ---
    if state == SessionState.idle:
        services = await _get_active_services(db, tenant.id)
        if not services:
            msg = ("عذراً، لا توجد خدمات متاحة حالياً." if lang == "ar"
                   else ("Нет доступных услуг." if lang == "ru" else "No services available."))
            return (msg, None)
        if not tenant.is_accepting_queue:
            msg = ("عذراً، الطابور مغلق حالياً." if lang == "ar"
                   else ("Очередь закрыта." if lang == "ru" else "Queue is currently closed."))
            return (msg, None)

        session.state = SessionState.selecting_service
        session.context = {"service_ids": [str(s.id) for s in services]}
        welcome = whatsapp_service.msg_welcome(_service_names(services, lang), lang)
        return (welcome, services)

    # --- SELECTING SERVICE ---
    if state == SessionState.selecting_service:
        service_ids = session.context.get("service_ids", [])
        selected_service = None

        # Interactive list reply sends service UUID as text
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
            tl = text.lower()
            for svc in services:
                if (tl in svc.name_ar.lower()
                        or tl in (svc.name_en or "").lower()
                        or tl in (svc.name_ru or "").lower()):
                    selected_service = svc
                    break

        if not selected_service:
            return (whatsapp_service.msg_invalid_service(lang), None)

        existing = await _get_active_queue_entry(db, tenant.id, customer.id)
        if existing:
            return (whatsapp_service.msg_already_in_queue(lang), None)

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
        return (whatsapp_service.msg_queued(position or 1, eta, lang), None)

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
            return (whatsapp_service.msg_cancelled(lang), None)

        entry_id_str = session.context.get("entry_id")
        if entry_id_str:
            position = await queue_service.get_queue_position(
                redis, tenant.id, uuid.UUID(entry_id_str)
            )
            if position:
                return (whatsapp_service.msg_info(position, position * 20, lang), None)

        msg = ("أنت في الطابور. اكتب 'إلغاء' للخروج." if lang == "ar"
               else ("Вы в очереди. Напишите 'отмена' для отмены." if lang == "ru"
                     else "You are in the queue. Type 'cancel' to leave."))
        return (msg, None)

    # --- BEING SERVED ---
    if state == SessionState.being_served:
        msg = ("أنت يتم خدمتك حالياً." if lang == "ar"
               else ("Вас обслуживают." if lang == "ru" else "You are currently being served."))
        return (msg, None)

    # --- DONE ---
    if state == SessionState.done:
        session.state = SessionState.idle
        session.context = {}
        services = await _get_active_services(db, tenant.id)
        welcome = whatsapp_service.msg_welcome(_service_names(services, lang), lang)
        return (welcome, services)

    return (None, None)


# ---------------------------------------------------------------------------
# Notification senders (called from queue_service)
# ---------------------------------------------------------------------------


async def send_upcoming_notification(
    db: AsyncSession,
    redis: Redis,
    entry: QueueEntry,
    tenant: Tenant,
) -> None:
    """Send 'your turn is coming' notification (position 3)."""
    customer = await db.get(Customer, entry.customer_id)
    if not customer or not tenant.d360_api_key:
        return
    lang = customer.preferred_language
    await whatsapp_service.send_message(
        d360_api_key=tenant.d360_api_key,
        to_phone=customer.phone,
        text=whatsapp_service.msg_upcoming(lang),
    )


async def send_called_notification(
    db: AsyncSession,
    entry: QueueEntry,
    tenant: Tenant,
) -> None:
    """Send 'it's your turn' notification when called."""
    customer = await db.get(Customer, entry.customer_id)
    if not customer or not tenant.d360_api_key:
        return
    lang = customer.preferred_language
    await whatsapp_service.send_message(
        d360_api_key=tenant.d360_api_key,
        to_phone=customer.phone,
        text=whatsapp_service.msg_called(lang),
    )

    from app.models.whatsapp_session import WhatsAppSession as WAS
    result = await db.execute(
        select(WAS).where(
            and_(WAS.tenant_id == tenant.id, WAS.customer_id == customer.id)
        )
    )
    session = result.scalar_one_or_none()
    if session:
        session.state = SessionState.being_served
        await db.commit()
