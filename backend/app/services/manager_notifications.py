"""Notifications to the business owner (manager) about bookings and cancellations."""
from datetime import datetime
from zoneinfo import ZoneInfo

import structlog

from app.models.tenant import Tenant
from app.models.appointment import Appointment
from app.models.service import Service
from app.models.customer import Customer

logger = structlog.get_logger(__name__)
KSA_TZ = ZoneInfo("Asia/Riyadh")


def _booking_msg(customer: Customer, service: Service | None, scheduled_at: datetime, action: str) -> dict[str, str]:
    local = scheduled_at.astimezone(KSA_TZ)
    date_str = local.strftime("%-d %b %Y")
    time_str = local.strftime("%H:%M")
    phone = customer.phone
    name = customer.name or phone

    svc_ar = service.name_ar if service else "—"
    svc_en = service.name_en if service else "—"
    svc_ru = (service.name_ru or service.name_en) if service else "—"

    if action == "booked":
        return {
            "ar": f"📅 حجز جديد!\n👤 {name} ({phone})\n🔧 {svc_ar}\n⏰ {date_str} الساعة {time_str}",
            "en": f"📅 New booking!\n👤 {name} ({phone})\n🔧 {svc_en}\n⏰ {date_str} at {time_str}",
            "ru": f"📅 Новая запись!\n👤 {name} ({phone})\n🔧 {svc_ru}\n⏰ {date_str} в {time_str}",
        }
    else:  # cancelled
        return {
            "ar": f"❌ تم إلغاء الحجز\n👤 {name} ({phone})\n🔧 {svc_ar}\n⏰ {date_str} الساعة {time_str}",
            "en": f"❌ Booking cancelled\n👤 {name} ({phone})\n🔧 {svc_en}\n⏰ {date_str} at {time_str}",
            "ru": f"❌ Запись отменена\n👤 {name} ({phone})\n🔧 {svc_ru}\n⏰ {date_str} в {time_str}",
        }


async def notify_manager(
    tenant: Tenant,
    customer: Customer,
    appointment: Appointment,
    service: Service | None,
    action: str,  # "booked" | "cancelled"
) -> None:
    """Send booking/cancellation notification to the manager."""
    # Determine manager's preferred language (default en)
    lang = "en"
    msgs = _booking_msg(customer, service, appointment.scheduled_at, action)
    text = msgs.get(lang, msgs["en"])

    sent = False

    # 1. Telegram — manager has linked their chat_id
    if tenant.telegram_bot_token and tenant.manager_telegram_chat_id:
        from app.services.telegram_service import send_message
        ok = await send_message(
            bot_token=tenant.telegram_bot_token,
            chat_id=tenant.manager_telegram_chat_id,
            text=text,
        )
        if ok:
            sent = True
            logger.info("Manager notified via Telegram", tenant_id=str(tenant.id), action=action)

    # 2. WhatsApp — send to tenant.phone via their own d360 credentials
    if not sent and tenant.d360_api_key and tenant.phone:
        from app.services.whatsapp_service import send_message as wa_send
        ok = await wa_send(
            d360_api_key=tenant.d360_api_key,
            to_phone=tenant.phone,
            text=text,
        )
        if ok:
            logger.info("Manager notified via WhatsApp", tenant_id=str(tenant.id), action=action)
