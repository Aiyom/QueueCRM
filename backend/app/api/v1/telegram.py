"""Telegram webhook endpoint — one per tenant (identified by tenant_id in URL)."""
import uuid
import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from sqlalchemy import select

from app.core.deps import DBSession, RedisConn, TenantAdmin, get_tenant_id
from app.models.tenant import Tenant
from app.services import telegram_bot_service
from app.services.telegram_service import set_webhook
from app.core.config import settings

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["telegram"])


@router.post("/telegram/{tenant_id}/webhook")
async def telegram_webhook(
    tenant_id: uuid.UUID,
    request: Request,
    db: DBSession,
    redis: RedisConn,
    background_tasks: BackgroundTasks,
):
    """Receive updates from Telegram for a specific tenant's bot."""
    tenant = await db.get(Tenant, tenant_id)
    if not tenant or not tenant.telegram_bot_token:
        raise HTTPException(404, detail="Tenant or bot not found")

    if not tenant.is_active:
        return {"ok": True}

    body = await request.json()
    message = body.get("message") or body.get("edited_message")
    if not message:
        return {"ok": True}

    chat_id = str(message.get("chat", {}).get("id", ""))
    text = (message.get("text") or "").strip()

    if not chat_id or not text:
        return {"ok": True}

    background_tasks.add_task(
        telegram_bot_service.handle_message,
        db,
        redis,
        tenant=tenant,
        chat_id=chat_id,
        message_text=text,
    )

    return {"ok": True}


@router.post("/telegram/setup-webhook")
async def setup_telegram_webhook(
    payload: TenantAdmin,
    db: DBSession,
):
    """Register this tenant's bot webhook URL with Telegram.

    Call once after saving the bot token in Settings.
    """
    tenant_id = get_tenant_id(payload)
    tenant = await db.scalar(select(Tenant).where(Tenant.id == tenant_id))
    if not tenant or not tenant.telegram_bot_token:
        raise HTTPException(400, detail="Telegram bot token not configured")

    webhook_url = f"{settings.PUBLIC_APP_URL}/api/v1/telegram/{tenant_id}/webhook"
    ok = await set_webhook(bot_token=tenant.telegram_bot_token, webhook_url=webhook_url)
    if not ok:
        raise HTTPException(502, detail="Failed to register webhook with Telegram")

    return {"ok": True, "webhook_url": webhook_url}
