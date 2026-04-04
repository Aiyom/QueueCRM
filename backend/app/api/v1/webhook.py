"""360dialog webhook endpoint."""
import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from sqlalchemy import select

from app.core.config import settings
from app.core.deps import DBSession, RedisConn
from app.models.tenant import Tenant
from app.services import bot_service

logger = structlog.get_logger(__name__)

# Webhook path uses WEBHOOK_SECRET_PATH for security (no token in body)
router = APIRouter(tags=["webhook"])


@router.post(f"/webhook/{{secret_path}}/{{channel_id}}")
async def whatsapp_webhook(
    secret_path: str,
    channel_id: str,
    request: Request,
    db: DBSession,
    redis: RedisConn,
    background_tasks: BackgroundTasks,
):
    """Receive inbound WhatsApp messages from 360dialog.

    URL pattern: /api/v1/webhook/{WEBHOOK_SECRET_PATH}/{channel_id}
    The channel_id maps to tenant.d360_channel_id.
    """
    if secret_path != settings.WEBHOOK_SECRET_PATH:
        raise HTTPException(status_code=403, detail="Invalid webhook path")

    body = await request.json()

    # Find tenant by channel_id
    result = await db.execute(
        select(Tenant).where(Tenant.d360_channel_id == channel_id)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        logger.warning("Webhook: unknown channel_id", channel_id=channel_id)
        return {"status": "ignored"}

    if not tenant.is_active:
        return {"status": "ignored"}

    # Parse messages
    messages = body.get("messages", [])
    for msg in messages:
        msg_type = msg.get("type")
        if msg_type != "text":
            continue

        phone = msg.get("from", "")
        text = msg.get("text", {}).get("body", "").strip()

        if not phone or not text:
            continue

        # Process in background to return 200 quickly
        background_tasks.add_task(
            bot_service.handle_message,
            db,
            redis,
            tenant=tenant,
            phone=phone,
            message_text=text,
        )

    return {"status": "ok"}
