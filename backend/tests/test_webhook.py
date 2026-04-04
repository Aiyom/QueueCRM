"""Tests for WhatsApp webhook and bot state machine."""
import uuid
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch

pytestmark = pytest.mark.asyncio

WEBHOOK_SECRET = "test-webhook-path"  # matches .env.test WEBHOOK_SECRET_PATH


@pytest.fixture
async def tenant_with_channel(db_session, sample_tenant):
    """Tenant with 360dialog channel configured."""
    sample_tenant.d360_api_key = "test-d360-key"
    sample_tenant.d360_channel_id = "test-channel-001"
    await db_session.commit()
    return sample_tenant


def _make_webhook_payload(phone: str, text: str) -> dict:
    return {
        "messages": [
            {
                "from": phone,
                "type": "text",
                "text": {"body": text},
            }
        ]
    }


class TestWebhookSecurity:
    async def test_wrong_secret_rejected(self, client: AsyncClient, tenant_with_channel):
        resp = await client.post(
            "/api/v1/webhook/wrong-secret/test-channel-001",
            json=_make_webhook_payload("+966501234567", "مرحبا"),
        )
        assert resp.status_code == 403

    async def test_unknown_channel_ignored(self, client: AsyncClient, tenant_with_channel):
        resp = await client.post(
            f"/api/v1/webhook/{WEBHOOK_SECRET}/unknown-channel",
            json=_make_webhook_payload("+966501234567", "hello"),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    async def test_valid_webhook_accepted(self, client: AsyncClient, tenant_with_channel):
        with patch(
            "app.services.whatsapp_service.send_message",
            new_callable=AsyncMock,
            return_value=True,
        ):
            resp = await client.post(
                f"/api/v1/webhook/{WEBHOOK_SECRET}/test-channel-001",
                json=_make_webhook_payload("+966501234567", "مرحبا"),
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestBotStateMachine:
    async def test_idle_to_selecting(self, db_session, redis, tenant_with_channel):
        """IDLE → message → show services."""
        from app.services.bot_service import handle_message
        from app.models.service import Service

        svc = Service(
            id=uuid.uuid4(),
            tenant_id=tenant_with_channel.id,
            name_ar="تغيير زيت",
            name_en="Oil Change",
            avg_duration_minutes=30,
        )
        db_session.add(svc)
        await db_session.commit()

        with patch(
            "app.services.whatsapp_service.send_message",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_send:
            await handle_message(
                db_session,
                redis,
                tenant=tenant_with_channel,
                phone="+966501234567",
                message_text="مرحبا",
            )

        mock_send.assert_called_once()
        call_args = mock_send.call_args
        assert "تغيير زيت" in call_args.kwargs["text"] or "تغيير زيت" in str(call_args)

    async def test_select_service_by_number(self, db_session, redis, tenant_with_channel):
        """SELECTING_SERVICE → '1' → join queue."""
        from app.services.bot_service import handle_message
        from app.models.service import Service

        svc = Service(
            id=uuid.uuid4(),
            tenant_id=tenant_with_channel.id,
            name_ar="غسيل سيارة",
            name_en="Car Wash",
            avg_duration_minutes=20,
        )
        db_session.add(svc)
        await db_session.commit()

        phone = "+966509876543"

        with patch("app.services.whatsapp_service.send_message", new_callable=AsyncMock, return_value=True):
            # First message → show services
            await handle_message(
                db_session, redis, tenant=tenant_with_channel, phone=phone, message_text="hello"
            )
            # Select service 1
            await handle_message(
                db_session, redis, tenant=tenant_with_channel, phone=phone, message_text="1"
            )

        # Customer should now be in queue
        from app.services.queue_service import get_queue_length
        length = await get_queue_length(redis, tenant_with_channel.id)
        assert length == 1

    async def test_cancel_from_queue(self, db_session, redis, tenant_with_channel):
        """IN_QUEUE → 'إلغاء' → cancelled."""
        from app.services.bot_service import handle_message
        from app.models.service import Service

        svc = Service(
            id=uuid.uuid4(),
            tenant_id=tenant_with_channel.id,
            name_ar="فحص شامل",
            name_en="Full Inspection",
            avg_duration_minutes=45,
        )
        db_session.add(svc)
        await db_session.commit()

        phone = "+966500011122"

        with patch("app.services.whatsapp_service.send_message", new_callable=AsyncMock, return_value=True):
            # Welcome
            await handle_message(db_session, redis, tenant=tenant_with_channel, phone=phone, message_text="hi")
            # Select
            await handle_message(db_session, redis, tenant=tenant_with_channel, phone=phone, message_text="1")
            # Cancel
            await handle_message(db_session, redis, tenant=tenant_with_channel, phone=phone, message_text="إلغاء")

        # Queue should be empty
        from app.services.queue_service import get_queue_length
        length = await get_queue_length(redis, tenant_with_channel.id)
        assert length == 0
