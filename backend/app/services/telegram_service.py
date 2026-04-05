"""Telegram Bot API integration: send messages via httpx (no heavy framework)."""
import structlog
import httpx

logger = structlog.get_logger(__name__)

TELEGRAM_API = "https://api.telegram.org"


async def send_message(*, bot_token: str, chat_id: str, text: str) -> bool:
    """Send a text message to a Telegram chat. Returns True on success."""
    url = f"{TELEGRAM_API}/bot{bot_token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json={"chat_id": chat_id, "text": text})
            resp.raise_for_status()
            logger.info("Telegram message sent", chat_id=chat_id)
            return True
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Telegram send failed",
            status=exc.response.status_code,
            body=exc.response.text[:200],
        )
        return False
    except Exception as exc:
        logger.error("Telegram send error", error=str(exc))
        return False


async def send_with_keyboard(
    *, bot_token: str, chat_id: str, text: str, keyboard: list[list[dict]]
) -> bool:
    """Send message with inline keyboard buttons."""
    url = f"{TELEGRAM_API}/bot{bot_token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "reply_markup": {"inline_keyboard": keyboard},
            })
            resp.raise_for_status()
            return True
    except Exception as exc:
        logger.error("Telegram send_with_keyboard error", error=str(exc))
        return False


async def answer_callback_query(*, bot_token: str, callback_query_id: str) -> None:
    """Dismiss the loading spinner on an inline button press."""
    url = f"{TELEGRAM_API}/bot{bot_token}/answerCallbackQuery"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(url, json={"callback_query_id": callback_query_id})
    except Exception:
        pass


async def set_webhook(*, bot_token: str, webhook_url: str) -> bool:
    """Register webhook URL with Telegram. Call once after bot token is saved."""
    url = f"{TELEGRAM_API}/bot{bot_token}/setWebhook"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json={"url": webhook_url})
            resp.raise_for_status()
            data = resp.json()
            ok = data.get("ok", False)
            logger.info("Telegram webhook set", ok=ok, url=webhook_url)
            return ok
    except Exception as exc:
        logger.error("Telegram setWebhook error", error=str(exc))
        return False


# ---------------------------------------------------------------------------
# Message templates (mirrors whatsapp_service templates + RU support)
# ---------------------------------------------------------------------------


def msg_select_language() -> str:
    return "🌐 Choose language / اختر اللغة / Выберите язык"


# ---------------------------------------------------------------------------
# Main menu (after language/phone)
# ---------------------------------------------------------------------------

def msg_main_menu(lang: str = "ar") -> str:
    if lang == "ar":
        return "مرحباً! 👋 ماذا تريد؟"
    if lang == "ru":
        return "Привет! 👋 Что вы хотите сделать?"
    return "Hello! 👋 What would you like to do?"


def main_menu_keyboard(lang: str = "ar") -> list[list[dict]]:
    labels = {
        "ar": ("🔴 الطابور الحالي", "📅 حجز موعد مسبق", "📋 مواعيدي"),
        "ru": ("🔴 Живая очередь", "📅 Записаться", "📋 Мои записи"),
        "en": ("🔴 Live Queue", "📅 Book Appointment", "📋 My Appointments"),
    }
    live, book, my = labels.get(lang, labels["en"])
    return [
        [{"text": live, "callback_data": "menu:queue"}],
        [{"text": book, "callback_data": "menu:book"}],
        [{"text": my,   "callback_data": "menu:my_appointments"}],
    ]


# ---------------------------------------------------------------------------
# Booking flow messages
# ---------------------------------------------------------------------------

def msg_pick_date(lang: str = "ar") -> str:
    if lang == "ar":
        return "📅 اختر التاريخ:"
    if lang == "ru":
        return "📅 Выберите дату:"
    return "📅 Choose a date:"


def msg_pick_service(lang: str = "ar") -> str:
    if lang == "ar":
        return "🔧 اختر الخدمة:"
    if lang == "ru":
        return "🔧 Выберите услугу:"
    return "🔧 Choose a service:"


def msg_pick_time(lang: str = "ar") -> str:
    if lang == "ar":
        return "⏰ اختر الوقت المتاح:"
    if lang == "ru":
        return "⏰ Выберите доступное время:"
    return "⏰ Choose an available time slot:"


def msg_no_slots(lang: str = "ar") -> str:
    if lang == "ar":
        return "😔 لا توجد أوقات متاحة في هذا اليوم. اختر يوماً آخر:"
    if lang == "ru":
        return "😔 Нет свободных слотов в этот день. Выберите другую дату:"
    return "😔 No available slots for this day. Please choose another date:"


def msg_no_working_days(lang: str = "ar") -> str:
    if lang == "ar":
        return "😔 لا توجد أيام عمل متاحة قريباً. يرجى المحاولة لاحقاً."
    if lang == "ru":
        return "😔 Нет доступных рабочих дней. Попробуйте позже."
    return "😔 No working days available soon. Please try again later."


def msg_booking_confirmed(date_str: str, time_str: str, service_name: str, lang: str = "ar") -> str:
    svc = f" — {service_name}" if service_name else ""
    if lang == "ar":
        return f"✅ تم تأكيد موعدك!\n📅 {date_str} الساعة {time_str}{svc}\nسنذكرك قبل ساعة."
    if lang == "ru":
        return f"✅ Запись подтверждена!\n📅 {date_str} в {time_str}{svc}\nНапомним за час."
    return f"✅ Appointment confirmed!\n📅 {date_str} at {time_str}{svc}\nWe'll remind you 1 hour before."


def msg_my_appointments_empty(lang: str = "ar") -> str:
    if lang == "ar":
        return "📋 ليس لديك مواعيد قادمة."
    if lang == "ru":
        return "📋 У вас нет предстоящих записей."
    return "📋 You have no upcoming appointments."


def msg_appointment_cancelled(lang: str = "ar") -> str:
    if lang == "ar":
        return "✅ تم إلغاء الموعد."
    if lang == "ru":
        return "✅ Запись отменена."
    return "✅ Appointment cancelled."


def msg_cancel_too_late(lang: str = "ar") -> str:
    if lang == "ar":
        return "⚠️ لا يمكن الإلغاء قبل أقل من ساعتين من الموعد."
    if lang == "ru":
        return "⚠️ Отмена невозможна менее чем за 2 часа до визита."
    return "⚠️ Cannot cancel less than 2 hours before the appointment."


def msg_welcome(service_names: list[str], lang: str = "ar") -> str:
    services = "\n".join(f"{i+1}. {name}" for i, name in enumerate(service_names))
    if lang == "ar":
        return "مرحباً بك! 👋\nيرجى اختيار الخدمة:\n\n" + services
    if lang == "ru":
        return "Добро пожаловать! 👋\nВыберите услугу:\n\n" + services
    return "Welcome! 👋\nPlease select a service:\n\n" + services


def msg_ask_phone(lang: str = "ar") -> str:
    if lang == "ar":
        return "مرحباً! 👋\nالرجاء إرسال رقم هاتفك بالصيغة الدولية (مثال: +966501234567)"
    if lang == "ru":
        return "Привет! 👋\nПожалуйста, отправьте ваш номер телефона в формате +966501234567"
    return "Hello! 👋\nPlease send your phone number in international format (e.g. +966501234567)"


def msg_phone_saved(lang: str = "ar") -> str:
    if lang == "ar":
        return "✅ تم حفظ رقمك. يرجى اختيار الخدمة:"
    if lang == "ru":
        return "✅ Номер сохранён. Выберите услугу:"
    return "✅ Phone saved. Please select a service:"


def msg_queued(position: int, eta_minutes: int, lang: str = "ar") -> str:
    if lang == "ar":
        return f"✅ تم إضافتك للطابور!\nموقعك: #{position}\nالوقت المتوقع: ~{eta_minutes} دقيقة"
    if lang == "ru":
        return f"✅ Вы добавлены в очередь!\nВаша позиция: #{position}\nПримерное ожидание: ~{eta_minutes} мин"
    return f"✅ Added to queue!\nPosition: #{position}\nEstimated wait: ~{eta_minutes} min"


def msg_upcoming(lang: str = "ar") -> str:
    if lang == "ar":
        return "⏰ دورك يقترب، يرجى الاستعداد!"
    if lang == "ru":
        return "⏰ Скоро ваша очередь, приготовьтесь!"
    return "⏰ Your turn is coming soon, please get ready!"


def msg_called(lang: str = "ar") -> str:
    if lang == "ar":
        return "🔔 حان دورك! تفضل الآن."
    if lang == "ru":
        return "🔔 Ваша очередь! Пожалуйста, подходите."
    return "🔔 It's your turn! Please come in now."


def msg_cancelled(lang: str = "ar") -> str:
    if lang == "ar":
        return "✅ تم إلغاء حجزك."
    if lang == "ru":
        return "✅ Ваша запись отменена."
    return "✅ Your booking has been cancelled."


def msg_already_in_queue(lang: str = "ar") -> str:
    if lang == "ar":
        return "أنت بالفعل في الطابور. اكتب 'إلغاء' للخروج."
    if lang == "ru":
        return "Вы уже в очереди. Напишите 'отмена' чтобы выйти."
    return "You are already in the queue. Type 'cancel' to leave."


def msg_invalid_service(lang: str = "ar") -> str:
    if lang == "ar":
        return "اختيار غير صحيح. يرجى إدخال رقم الخدمة."
    if lang == "ru":
        return "Неверный выбор. Введите номер услуги."
    return "Invalid selection. Please enter the service number."


def msg_info(position: int, eta_minutes: int, lang: str = "ar") -> str:
    if lang == "ar":
        return f"موقعك في الطابور: #{position}، الوقت المتوقع: ~{eta_minutes} دقيقة"
    if lang == "ru":
        return f"Ваша позиция в очереди: #{position}, ожидание: ~{eta_minutes} мин"
    return f"Queue position: #{position}, estimated wait: ~{eta_minutes} min"
