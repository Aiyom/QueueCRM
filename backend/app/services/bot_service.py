"""WhatsApp bot state machine."""
import uuid
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

CANCEL_KEYWORDS = {"إلغاء", "cancel", "الغاء", "يلغي", "إلغى"}


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
        # Reset if expired
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


def _detect_language(text: str) -> str:
    """Detect AR or EN based on presence of Arabic Unicode range."""
    arabic_chars = sum(1 for c in text if "\u0600" <= c <= "\u06ff")
    return "ar" if arabic_chars > len(text) * 0.2 else "en"


async def _get_active_services(
    db: AsyncSession, tenant_id: uuid.UUID
) -> list[Service]:
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
    phone: str,
    message_text: str,
) -> None:
    """Process incoming WhatsApp message and send reply."""
    text = message_text.strip()
    lang = _detect_language(text)
    d360_api_key = tenant.d360_api_key or ""

    # Get/create customer
    customer = await _get_or_create_customer(db, tenant.id, phone, lang)
    session = await _get_or_create_session(db, tenant.id, customer.id)

    reply = await _dispatch(db, redis, tenant, customer, session, text, lang)

    await db.commit()

    if reply and d360_api_key:
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
) -> Optional[str]:
    state = session.state

    # --- IDLE ---
    if state == SessionState.idle:
        services = await _get_active_services(db, tenant.id)
        if not services:
            return "عذراً، لا توجد خدمات متاحة حالياً." if lang == "ar" else "No services available."
        if not tenant.is_accepting_queue:
            return "عذراً، الطابور مغلق حالياً." if lang == "ar" else "Queue is currently closed."

        session.state = SessionState.selecting_service
        session.context = {"service_ids": [str(s.id) for s in services]}

        names = [s.name_ar if lang == "ar" else s.name_en for s in services]
        return whatsapp_service.msg_welcome(names, lang)

    # --- SELECTING SERVICE ---
    if state == SessionState.selecting_service:
        service_ids = session.context.get("service_ids", [])

        # Try numeric selection
        selected_service = None
        if text.isdigit():
            idx = int(text) - 1
            if 0 <= idx < len(service_ids):
                selected_service = await db.get(Service, uuid.UUID(service_ids[idx]))
        else:
            # Try name match
            services = await _get_active_services(db, tenant.id)
            for svc in services:
                if text.lower() in svc.name_ar.lower() or text.lower() in svc.name_en.lower():
                    selected_service = svc
                    break

        if not selected_service:
            return whatsapp_service.msg_invalid_service(lang)

        # Check for duplicate
        existing = await _get_active_queue_entry(db, tenant.id, customer.id)
        if existing:
            return whatsapp_service.msg_already_in_queue(lang)

        # Add to queue
        entry = await queue_service.add_to_queue(
            db, redis,
            tenant_id=tenant.id,
            customer_id=customer.id,
            service_id=selected_service.id,
        )

        position = await queue_service.get_queue_position(redis, tenant.id, entry.id)
        avg_min = selected_service.avg_duration_minutes
        eta = (position or 1) * avg_min

        session.state = SessionState.in_queue
        session.context = {"entry_id": str(entry.id)}

        return whatsapp_service.msg_queued(position or 1, eta, lang)

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
            return whatsapp_service.msg_cancelled(lang)

        # Show current position
        entry_id_str = session.context.get("entry_id")
        if entry_id_str:
            position = await queue_service.get_queue_position(
                redis, tenant.id, uuid.UUID(entry_id_str)
            )
            if position:
                return whatsapp_service.msg_info(position, position * 20, lang)

        return (
            "أنت في الطابور. اكتب 'إلغاء' للخروج."
            if lang == "ar"
            else "You are in the queue. Type 'cancel' to leave."
        )

    # --- BEING SERVED ---
    if state == SessionState.being_served:
        return (
            "أنت يتم خدمتك حالياً."
            if lang == "ar"
            else "You are currently being served."
        )

    # --- DONE ---
    if state == SessionState.done:
        # Reset to idle for next interaction
        session.state = SessionState.idle
        session.context = {}
        services = await _get_active_services(db, tenant.id)
        names = [s.name_ar if lang == "ar" else s.name_en for s in services]
        return whatsapp_service.msg_welcome(names, lang)

    return None


# ---------------------------------------------------------------------------
# Notification senders (called from queue endpoints or workers)
# ---------------------------------------------------------------------------


async def send_upcoming_notification(
    db: AsyncSession,
    redis: Redis,
    entry: QueueEntry,
    tenant: Tenant,
) -> None:
    """Send 'your turn is coming' notification to the customer at position 3."""
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

    # Transition session to being_served
    from app.models.whatsapp_session import WhatsAppSession as WAS
    from sqlalchemy import select as sa_select, and_ as sa_and
    result = await db.execute(
        sa_select(WAS).where(
            sa_and(WAS.tenant_id == tenant.id, WAS.customer_id == customer.id)
        )
    )
    session = result.scalar_one_or_none()
    if session:
        session.state = SessionState.being_served
        await db.commit()
