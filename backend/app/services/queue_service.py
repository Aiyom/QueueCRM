"""Queue business logic: Redis Sorted Set + DB persistence."""
import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from redis.asyncio import Redis
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.queue_entry import QueueEntry, QueueStatus
from app.models.customer import Customer
from app.models.service import Service
from app.models.tenant import Tenant
from sqlalchemy import select as sa_select

logger = structlog.get_logger(__name__)

# Redis key patterns
_QUEUE_KEY = "queue:{tenant_id}"        # Sorted Set — score = join timestamp (VIP: -86400)
_ETA_KEY = "avg_duration:{tenant_id}:{service_id}"  # cached avg duration in minutes

VIP_SCORE_OFFSET = 86400  # seconds — VIP gets this subtracted so they sort first


# ---------------------------------------------------------------------------
# Redis helpers
# ---------------------------------------------------------------------------


def _queue_key(tenant_id: uuid.UUID) -> str:
    return _QUEUE_KEY.format(tenant_id=str(tenant_id))


def _eta_key(tenant_id: uuid.UUID, service_id: uuid.UUID) -> str:
    return _ETA_KEY.format(tenant_id=str(tenant_id), service_id=str(service_id))


def _now_ts() -> float:
    return datetime.now(timezone.utc).timestamp()


# ---------------------------------------------------------------------------
# Startup: restore queue from DB
# ---------------------------------------------------------------------------


async def restore_queue_from_db(db: AsyncSession, redis: Redis) -> None:
    """On startup, repopulate Redis Sorted Sets from DB (waiting entries only)."""
    result = await db.execute(
        select(QueueEntry, Customer)
        .join(Customer, QueueEntry.customer_id == Customer.id)
        .where(QueueEntry.status == QueueStatus.waiting)
        .order_by(QueueEntry.created_at)
    )
    rows = result.all()

    # Group by tenant
    by_tenant: dict[str, list[tuple[str, float]]] = {}
    for entry, customer in rows:
        key = _queue_key(entry.tenant_id)
        score = entry.created_at.timestamp()
        if customer.is_vip:
            score -= VIP_SCORE_OFFSET
        by_tenant.setdefault(key, []).append((str(entry.id), score))

    pipe = redis.pipeline()
    for queue_key, members in by_tenant.items():
        pipe.delete(queue_key)
        for member_id, score in members:
            pipe.zadd(queue_key, {member_id: score})
    await pipe.execute()

    logger.info("Queue restored from DB", entries=len(rows))


# ---------------------------------------------------------------------------
# Core queue operations
# ---------------------------------------------------------------------------


async def add_to_queue(
    db: AsyncSession,
    redis: Redis,
    *,
    tenant_id: uuid.UUID,
    customer_id: uuid.UUID,
    service_id: Optional[uuid.UUID] = None,
) -> QueueEntry:
    """Create a QueueEntry and add to Redis Sorted Set."""
    # Validate customer belongs to tenant
    customer = await db.get(Customer, customer_id)
    if not customer or customer.tenant_id != tenant_id:
        raise ValueError("Customer not found")

    # Check for existing active entry (prevent duplicate)
    existing = await db.execute(
        select(QueueEntry).where(
            and_(
                QueueEntry.tenant_id == tenant_id,
                QueueEntry.customer_id == customer_id,
                QueueEntry.status.in_([QueueStatus.waiting, QueueStatus.called]),
            )
        )
    )
    if existing.scalar_one_or_none():
        raise ValueError("Customer already in queue")

    entry = QueueEntry(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        customer_id=customer_id,
        service_id=service_id,
        status=QueueStatus.waiting,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)

    # Add to Redis
    score = _now_ts()
    if customer.is_vip:
        score -= VIP_SCORE_OFFSET

    await redis.zadd(_queue_key(tenant_id), {str(entry.id): score})
    logger.info("Added to queue", entry_id=str(entry.id), tenant_id=str(tenant_id))
    return entry


async def get_queue_position(
    redis: Redis,
    tenant_id: uuid.UUID,
    entry_id: uuid.UUID,
) -> Optional[int]:
    """Return 1-based position in queue, or None if not found."""
    rank = await redis.zrank(_queue_key(tenant_id), str(entry_id))
    if rank is None:
        return None
    return rank + 1  # 0-indexed → 1-indexed


async def get_queue_length(redis: Redis, tenant_id: uuid.UUID) -> int:
    return await redis.zcard(_queue_key(tenant_id))


async def get_queue_entries(
    db: AsyncSession,
    redis: Redis,
    tenant_id: uuid.UUID,
) -> list[dict]:
    """Return ordered list of waiting queue entries with position and ETA."""
    # Get ordered IDs from Redis
    entry_ids = await redis.zrange(_queue_key(tenant_id), 0, -1)

    if not entry_ids:
        return []

    # Load DB records
    uuids = [uuid.UUID(eid) for eid in entry_ids]
    result = await db.execute(
        select(QueueEntry, Customer, Service)
        .join(Customer, QueueEntry.customer_id == Customer.id)
        .outerjoin(Service, QueueEntry.service_id == Service.id)
        .where(QueueEntry.id.in_(uuids))
    )
    rows = {str(row.QueueEntry.id): row for row in result.all()}

    output = []
    for position, eid in enumerate(entry_ids, start=1):
        row = rows.get(eid)
        if not row:
            continue
        entry, customer, service = row.QueueEntry, row.Customer, row.Service

        # ETA = position × avg_duration for this service
        avg_min = 30  # default
        if service:
            cached = await redis.get(_eta_key(tenant_id, service.id))
            avg_min = float(cached) if cached else service.avg_duration_minutes

        eta_minutes = position * avg_min

        output.append({
            "id": str(entry.id),
            "position": position,
            "status": entry.status.value,
            "eta_minutes": eta_minutes,
            "customer": {
                "id": str(customer.id),
                "phone": customer.phone,
                "name": customer.name,
                "is_vip": customer.is_vip,
            },
            "service": {
                "id": str(service.id),
                "name_ar": service.name_ar,
                "name_en": service.name_en,
                "name_ru": service.name_ru,
            } if service else None,
            "created_at": entry.created_at.isoformat(),
        })
    return output


async def call_next(
    db: AsyncSession,
    redis: Redis,
    tenant_id: uuid.UUID,
) -> Optional[QueueEntry]:
    """Pop the next entry from the queue and mark it as 'called'."""
    members = await redis.zrange(_queue_key(tenant_id), 0, 0)
    if not members:
        return None

    entry_id_str = members[0]
    await redis.zrem(_queue_key(tenant_id), entry_id_str)

    entry = await db.get(QueueEntry, uuid.UUID(entry_id_str))
    if not entry:
        return None

    entry.status = QueueStatus.called
    entry.called_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(entry)

    logger.info("Called next", entry_id=entry_id_str, tenant_id=str(tenant_id))

    # Send "it's your turn" notification via WhatsApp and Telegram
    tenant = await db.get(Tenant, tenant_id)
    if tenant:
        from app.services import bot_service, telegram_bot_service
        await bot_service.send_called_notification(db, entry, tenant)
        await telegram_bot_service.send_called_notification(db, entry, tenant)

    # Check if the next person in line should get "upcoming" notification
    upcoming_ids = await get_entries_to_notify(redis, tenant_id, notify_position=3)
    if upcoming_ids and tenant:
        upcoming_entry = await db.get(QueueEntry, uuid.UUID(upcoming_ids[0]))
        if upcoming_entry:
            from app.services import bot_service, telegram_bot_service
            await bot_service.send_upcoming_notification(db, redis, upcoming_entry, tenant)
            await telegram_bot_service.send_upcoming_notification(db, upcoming_entry, tenant)

    return entry


async def start_service(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    entry_id: uuid.UUID,
) -> QueueEntry:
    """Transition called → in_service."""
    entry = await db.get(QueueEntry, entry_id)
    if not entry or entry.tenant_id != tenant_id:
        raise ValueError("Entry not found")
    if entry.status != QueueStatus.called:
        raise ValueError(f"Cannot start service: status is {entry.status.value}")

    entry.status = QueueStatus.in_service
    entry.started_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(entry)
    return entry


async def finish_service(
    db: AsyncSession,
    redis: Redis,
    tenant_id: uuid.UUID,
    entry_id: uuid.UUID,
    amount: Optional[float] = None,
    notes: Optional[str] = None,
) -> QueueEntry:
    """Transition in_service → done. Updates avg_duration in Redis + customer stats."""
    entry = await db.get(QueueEntry, entry_id)
    if not entry or entry.tenant_id != tenant_id:
        raise ValueError("Entry not found")
    if entry.status != QueueStatus.in_service:
        raise ValueError(f"Cannot finish: status is {entry.status.value}")

    now = datetime.now(timezone.utc)
    entry.status = QueueStatus.done
    entry.finished_at = now
    if amount is not None:
        entry.amount = amount
    if notes is not None:
        entry.notes = notes

    # Update rolling avg_duration for service (last 10 completed)
    if entry.service_id and entry.started_at:
        duration_min = (now - entry.started_at).total_seconds() / 60
        await _update_avg_duration(db, redis, tenant_id, entry.service_id, duration_min)

    # Update customer stats
    customer = await db.get(Customer, entry.customer_id)
    if customer:
        customer.total_visits += 1
        if amount and amount > 0:
            customer.total_spent += amount
        customer.last_seen_at = now
        # Auto-promote to VIP if >= 10 visits
        if customer.total_visits >= 10 and not customer.vip_set_manually:
            customer.is_vip = True

    await db.commit()
    await db.refresh(entry)
    return entry


async def cancel_entry(
    db: AsyncSession,
    redis: Redis,
    tenant_id: uuid.UUID,
    entry_id: uuid.UUID,
) -> QueueEntry:
    """Cancel a waiting or called entry."""
    entry = await db.get(QueueEntry, entry_id)
    if not entry or entry.tenant_id != tenant_id:
        raise ValueError("Entry not found")
    if entry.status not in (QueueStatus.waiting, QueueStatus.called):
        raise ValueError(f"Cannot cancel: status is {entry.status.value}")

    entry.status = QueueStatus.cancelled
    await redis.zrem(_queue_key(tenant_id), str(entry_id))
    await db.commit()
    await db.refresh(entry)
    return entry


async def mark_no_show(
    db: AsyncSession,
    redis: Redis,
    tenant_id: uuid.UUID,
    entry_id: uuid.UUID,
) -> QueueEntry:
    """Mark a called entry as no_show."""
    entry = await db.get(QueueEntry, entry_id)
    if not entry or entry.tenant_id != tenant_id:
        raise ValueError("Entry not found")
    if entry.status != QueueStatus.called:
        raise ValueError(f"Cannot mark no_show: status is {entry.status.value}")

    entry.status = QueueStatus.no_show
    await redis.zrem(_queue_key(tenant_id), str(entry_id))
    await db.commit()
    await db.refresh(entry)
    return entry


# ---------------------------------------------------------------------------
# Avg duration (sliding window of last 10)
# ---------------------------------------------------------------------------


async def _update_avg_duration(
    db: AsyncSession,
    redis: Redis,
    tenant_id: uuid.UUID,
    service_id: uuid.UUID,
    new_duration_min: float,
) -> None:
    """Compute rolling average of last 10 durations for a service."""
    result = await db.execute(
        select(QueueEntry.started_at, QueueEntry.finished_at)
        .where(
            and_(
                QueueEntry.tenant_id == tenant_id,
                QueueEntry.service_id == service_id,
                QueueEntry.status == QueueStatus.done,
                QueueEntry.started_at.isnot(None),
                QueueEntry.finished_at.isnot(None),
            )
        )
        .order_by(QueueEntry.finished_at.desc())
        .limit(10)
    )
    rows = result.all()
    durations = [
        (r.finished_at - r.started_at).total_seconds() / 60
        for r in rows
        if r.started_at and r.finished_at
    ]
    # Include the new one if not yet committed
    if new_duration_min > 0:
        durations.insert(0, new_duration_min)
    durations = durations[:10]

    if durations:
        avg = sum(durations) / len(durations)
        # Cache for 24h
        await redis.set(_eta_key(tenant_id, service_id), avg, ex=86400)

        # Also update Service.avg_duration_minutes in DB
        service = await db.get(Service, service_id)
        if service:
            service.avg_duration_minutes = round(avg)


# ---------------------------------------------------------------------------
# Upcoming notification check
# ---------------------------------------------------------------------------


async def get_entries_to_notify(
    redis: Redis,
    tenant_id: uuid.UUID,
    notify_position: int = 3,
) -> list[str]:
    """Return entry_ids that are at position `notify_position` (for upcoming alert)."""
    # 0-indexed: position 3 = index 2
    members = await redis.zrange(
        _queue_key(tenant_id), notify_position - 1, notify_position - 1
    )
    return list(members)
