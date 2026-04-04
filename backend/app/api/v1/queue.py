"""Queue management endpoints + WebSocket."""
import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status

from app.core.deps import DBSession, RedisConn, TenantUser, TenantAdmin, get_tenant_id
from app.models.queue_entry import QueueStatus
from app.models.tenant import Tenant
from app.schemas.queue import (
    AddToQueueRequest,
    FinishServiceRequest,
    QueueEntryDetail,
    QueueStatsResponse,
)
from app.services import queue_service
from app.services.websocket_manager import ws_manager
from sqlalchemy import select, func, and_

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/queue", tags=["queue"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _broadcast_queue_update(
    db, redis, tenant_id: uuid.UUID, event: str, data: dict
) -> None:
    queue = await queue_service.get_queue_entries(db, redis, tenant_id)
    await ws_manager.broadcast(
        tenant_id,
        {
            "event": event,
            "queue": queue,
            **data,
        },
    )


# ---------------------------------------------------------------------------
# Queue CRUD
# ---------------------------------------------------------------------------


@router.get("/", summary="Get current queue")
async def get_queue(payload: TenantUser, db: DBSession, redis: RedisConn):
    """Return the ordered waiting queue for this tenant."""
    tenant_id = get_tenant_id(payload)
    return await queue_service.get_queue_entries(db, redis, tenant_id)


@router.post("/add", response_model=QueueEntryDetail, status_code=status.HTTP_201_CREATED)
async def add_to_queue(
    body: AddToQueueRequest,
    payload: TenantUser,
    db: DBSession,
    redis: RedisConn,
):
    """Add a customer to the queue."""
    tenant_id = get_tenant_id(payload)
    try:
        entry = await queue_service.add_to_queue(
            db, redis,
            tenant_id=tenant_id,
            customer_id=body.customer_id,
            service_id=body.service_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await _broadcast_queue_update(db, redis, tenant_id, "queue_updated", {
        "action": "added",
        "entry_id": str(entry.id),
    })

    # Check upcoming notifications
    upcoming = await queue_service.get_entries_to_notify(redis, tenant_id)
    for eid in upcoming:
        await ws_manager.broadcast(tenant_id, {
            "event": "notify_upcoming",
            "entry_id": eid,
            "tenant_id": str(tenant_id),
        })

    return QueueEntryDetail.model_validate(entry)


@router.post("/call-next", response_model=QueueEntryDetail)
async def call_next(payload: TenantUser, db: DBSession, redis: RedisConn):
    """Call the next customer in queue."""
    tenant_id = get_tenant_id(payload)
    entry = await queue_service.call_next(db, redis, tenant_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Queue is empty")

    await _broadcast_queue_update(db, redis, tenant_id, "queue_updated", {
        "action": "called",
        "entry_id": str(entry.id),
        "tenant_id": str(tenant_id),
    })
    await ws_manager.broadcast(tenant_id, {
        "event": "called",
        "entry_id": str(entry.id),
        "customer_id": str(entry.customer_id),
        "tenant_id": str(tenant_id),
    })

    return QueueEntryDetail.model_validate(entry)


@router.post("/{entry_id}/start", response_model=QueueEntryDetail)
async def start_service(
    entry_id: uuid.UUID,
    payload: TenantUser,
    db: DBSession,
    redis: RedisConn,
):
    """Mark called → in_service."""
    tenant_id = get_tenant_id(payload)
    try:
        entry = await queue_service.start_service(db, tenant_id, entry_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await _broadcast_queue_update(db, redis, tenant_id, "queue_updated", {
        "action": "in_service",
        "entry_id": str(entry.id),
    })
    return QueueEntryDetail.model_validate(entry)


@router.post("/{entry_id}/finish", response_model=QueueEntryDetail)
async def finish_service(
    entry_id: uuid.UUID,
    body: FinishServiceRequest,
    payload: TenantUser,
    db: DBSession,
    redis: RedisConn,
):
    """Mark in_service → done. Optional amount and notes."""
    tenant_id = get_tenant_id(payload)
    try:
        entry = await queue_service.finish_service(
            db, redis, tenant_id, entry_id,
            amount=body.amount,
            notes=body.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await _broadcast_queue_update(db, redis, tenant_id, "queue_updated", {
        "action": "done",
        "entry_id": str(entry.id),
    })
    return QueueEntryDetail.model_validate(entry)


@router.post("/{entry_id}/cancel", response_model=QueueEntryDetail)
async def cancel_entry(
    entry_id: uuid.UUID,
    payload: TenantUser,
    db: DBSession,
    redis: RedisConn,
):
    """Cancel a waiting or called entry."""
    tenant_id = get_tenant_id(payload)
    try:
        entry = await queue_service.cancel_entry(db, redis, tenant_id, entry_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await _broadcast_queue_update(db, redis, tenant_id, "queue_updated", {
        "action": "cancelled",
        "entry_id": str(entry.id),
    })
    return QueueEntryDetail.model_validate(entry)


@router.post("/{entry_id}/no-show", response_model=QueueEntryDetail)
async def mark_no_show(
    entry_id: uuid.UUID,
    payload: TenantUser,
    db: DBSession,
    redis: RedisConn,
):
    """Mark called entry as no-show."""
    tenant_id = get_tenant_id(payload)
    try:
        entry = await queue_service.mark_no_show(db, redis, tenant_id, entry_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await _broadcast_queue_update(db, redis, tenant_id, "queue_updated", {
        "action": "no_show",
        "entry_id": str(entry.id),
    })
    return QueueEntryDetail.model_validate(entry)


# ---------------------------------------------------------------------------
# Queue stats
# ---------------------------------------------------------------------------


@router.get("/stats", response_model=QueueStatsResponse)
async def queue_stats(payload: TenantUser, db: DBSession, redis: RedisConn):
    """Return summary stats for the current tenant's queue."""
    from app.models.queue_entry import QueueEntry
    from app.models.tenant import Tenant as TenantModel

    tenant_id = get_tenant_id(payload)

    # Status counts
    result = await db.execute(
        select(QueueEntry.status, func.count(QueueEntry.id))
        .where(QueueEntry.tenant_id == tenant_id)
        .where(QueueEntry.status.in_([
            QueueStatus.waiting, QueueStatus.called, QueueStatus.in_service
        ]))
        .group_by(QueueEntry.status)
    )
    counts = {row[0]: row[1] for row in result.all()}

    # Avg wait time (last 10 done entries)
    from sqlalchemy import cast
    from sqlalchemy.types import Float
    from app.models.queue_entry import QueueEntry as QE
    wait_result = await db.execute(
        select(QE.created_at, QE.called_at)
        .where(
            and_(
                QE.tenant_id == tenant_id,
                QE.status == QueueStatus.done,
                QE.called_at.isnot(None),
            )
        )
        .order_by(QE.called_at.desc())
        .limit(10)
    )
    wait_rows = wait_result.all()
    avg_wait = 0.0
    if wait_rows:
        waits = [
            (r.called_at - r.created_at).total_seconds() / 60
            for r in wait_rows
            if r.called_at and r.created_at
        ]
        avg_wait = sum(waits) / len(waits) if waits else 0.0

    # is_accepting_queue from tenant
    tenant_result = await db.execute(
        select(TenantModel.is_accepting_queue).where(TenantModel.id == tenant_id)
    )
    is_accepting = tenant_result.scalar_one_or_none() or False

    return QueueStatsResponse(
        total_waiting=counts.get(QueueStatus.waiting, 0),
        total_called=counts.get(QueueStatus.called, 0),
        total_in_service=counts.get(QueueStatus.in_service, 0),
        avg_wait_time_minutes=round(avg_wait, 1),
        is_accepting_queue=is_accepting,
    )


@router.patch("/toggle-accepting", status_code=200)
async def toggle_accepting_queue(
    payload: TenantAdmin,
    db: DBSession,
):
    """Admin: toggle is_accepting_queue on/off."""
    from app.models.tenant import Tenant as TenantModel
    tenant_id = get_tenant_id(payload)
    tenant = await db.get(TenantModel, tenant_id)
    if not tenant:
        raise HTTPException(404, detail="Tenant not found")
    tenant.is_accepting_queue = not tenant.is_accepting_queue
    await db.commit()
    return {"is_accepting_queue": tenant.is_accepting_queue}


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------


@router.websocket("/ws/{tenant_id}")
async def queue_websocket(
    websocket: WebSocket,
    tenant_id: uuid.UUID,
):
    """Real-time queue updates for dashboard. Auth via query param token."""
    # Simple auth: validate token from query param
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001)
        return

    try:
        from app.core.security import decode_token
        payload = decode_token(token)
        if payload.get("tid") != str(tenant_id) and payload.get("role") != "super_admin":
            await websocket.close(code=4003)
            return
    except Exception:
        await websocket.close(code=4001)
        return

    await ws_manager.connect(tenant_id, websocket)
    try:
        while True:
            # Keep alive — client sends pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(tenant_id, websocket)
