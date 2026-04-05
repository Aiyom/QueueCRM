"""Telegram webhook endpoint — one per tenant (identified by tenant_id in URL)."""
import uuid
import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from sqlalchemy import select

from app.core.deps import DBSession, RedisConn, TenantAdmin, get_tenant_id, get_redis_pool
from app.core.database import AsyncSessionLocal
from app.models.tenant import Tenant
from app.services import telegram_bot_service
from app.services.telegram_service import set_webhook
from app.core.config import settings

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["telegram"])


async def _process_telegram_update(
    tenant_id: uuid.UUID,
    chat_id: str,
    text: str,
    callback_query_id: str | None = None,
) -> None:
    """Run in background — creates its own DB session to avoid request-scope issues."""
    redis = get_redis_pool()
    async with AsyncSessionLocal() as db:
        try:
            tenant = await db.get(Tenant, tenant_id)
            if not tenant or not tenant.telegram_bot_token or not tenant.is_active:
                return
            # Acknowledge the button press immediately (removes spinner)
            if callback_query_id:
                from app.services.telegram_service import answer_callback_query
                await answer_callback_query(
                    bot_token=tenant.telegram_bot_token,
                    callback_query_id=callback_query_id,
                )
            await telegram_bot_service.handle_message(
                db, redis, tenant=tenant, chat_id=chat_id, message_text=text
            )
        except Exception as exc:
            logger.error("Telegram background handler error", error=str(exc))


@router.post("/telegram/{tenant_id}/webhook")
async def telegram_webhook(
    tenant_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
):
    """Receive updates from Telegram for a specific tenant's bot."""
    body = await request.json()

    # Inline keyboard button press
    if "callback_query" in body:
        cq = body["callback_query"]
        chat_id = str(cq.get("message", {}).get("chat", {}).get("id", ""))
        text = (cq.get("data") or "").strip()
        callback_query_id = cq.get("id", "")
        if chat_id and text:
            background_tasks.add_task(
                _process_telegram_update, tenant_id, chat_id, text, callback_query_id
            )
        return {"ok": True}

    # Regular text message
    message = body.get("message") or body.get("edited_message")
    if not message:
        return {"ok": True}

    chat_id = str(message.get("chat", {}).get("id", ""))
    text = (message.get("text") or "").strip()

    if not chat_id or not text:
        return {"ok": True}

    background_tasks.add_task(_process_telegram_update, tenant_id, chat_id, text)

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
