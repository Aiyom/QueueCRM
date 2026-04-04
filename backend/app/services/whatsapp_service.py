"""360dialog WhatsApp integration: send messages."""
import structlog
import httpx

from app.core.config import settings

logger = structlog.get_logger(__name__)


async def send_message(
    *,
    d360_api_key: str,
    to_phone: str,
    text: str,
) -> bool:
    """Send a text message via 360dialog On-Premise API.

    Returns True on success, False on failure.
    """
    url = f"{settings.D360_API_URL}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone,
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={
                    "D360-API-KEY": d360_api_key,
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            logger.info("WhatsApp message sent", to=to_phone)
            return True
    except httpx.HTTPStatusError as exc:
        logger.error(
            "WhatsApp send failed",
            status=exc.response.status_code,
            body=exc.response.text[:200],
        )
        return False
    except Exception as exc:
        logger.error("WhatsApp send error", error=str(exc))
        return False


# ---------------------------------------------------------------------------
# Message templates
# ---------------------------------------------------------------------------


def msg_welcome(service_names: list[str], lang: str = "ar") -> str:
    if lang == "ar":
        services = "\n".join(
            f"{i+1}. {name}" for i, name in enumerate(service_names)
        )
        return (
            "مرحباً بك! 👋\nيرجى اختيار الخدمة المطلوبة:\n\n"
            + services
        )
    services = "\n".join(f"{i+1}. {name}" for i, name in enumerate(service_names))
    return "Welcome! 👋\nPlease select a service:\n\n" + services


def msg_queued(position: int, eta_minutes: int, lang: str = "ar") -> str:
    if lang == "ar":
        return (
            f"✅ تم إضافتك للطابور!\n"
            f"موقعك: #{position}\n"
            f"الوقت المتوقع: ~{eta_minutes} دقيقة"
        )
    return (
        f"✅ You have been added to the queue!\n"
        f"Your position: #{position}\n"
        f"Estimated wait: ~{eta_minutes} min"
    )


def msg_upcoming(lang: str = "ar") -> str:
    if lang == "ar":
        return "⏰ دورك يقترب، يرجى الاستعداد!"
    return "⏰ Your turn is coming soon, please get ready!"


def msg_called(lang: str = "ar") -> str:
    if lang == "ar":
        return "🔔 حان دورك! تفضل الآن."
    return "🔔 It's your turn! Please come in now."


def msg_cancelled(lang: str = "ar") -> str:
    if lang == "ar":
        return "✅ تم إلغاء حجزك."
    return "✅ Your booking has been cancelled."


def msg_already_in_queue(lang: str = "ar") -> str:
    if lang == "ar":
        return "أنت بالفعل في الطابور. اكتب 'إلغاء' للخروج."
    return "You are already in the queue. Type 'cancel' to leave."


def msg_invalid_service(lang: str = "ar") -> str:
    if lang == "ar":
        return "اختيار غير صحيح. يرجى إدخال رقم الخدمة."
    return "Invalid selection. Please enter the service number."


def msg_info(position: int, eta_minutes: int, lang: str = "ar") -> str:
    if lang == "ar":
        return f"موقعك في الطابور: #{position}، الوقت المتوقع: ~{eta_minutes} دقيقة"
    return f"Your queue position: #{position}, estimated wait: ~{eta_minutes} min"
