# QueueCRM KSA — Project Context

## Что это
SaaS-система управления очередями + CRM для автобизнеса в Саудовской Аравии.
Клиенты взаимодействуют через WhatsApp (без установки приложений).
Бизнес управляет очередями через веб-дашборд.

## Стек
- Backend: Python 3.12, FastAPI, SQLAlchemy 2.0 async, Alembic
- Database: PostgreSQL 16
- Cache / Queue: Redis 7 (Sorted Sets для очереди, Pub/Sub для realtime)
- WebSocket: FastAPI native WebSockets
- WhatsApp: 360dialog On-Premise API (Partner аккаунт — один на всех тенантов)
- Telegram: python-telegram-bot (aiogram) — опциональный канал, включается per-tenant
- Frontend: Vue 3, TypeScript, Vite, TanStack Query (@tanstack/vue-query), Pinia
- Auth: JWT (access 15min + refresh 7days, Redis whitelist для refresh tokens)
- Deploy target: Render (backend + static frontends) + Upstash (Redis)

## Структура проекта
/backend
  /app
    /api          — роутеры FastAPI
    /core         — config, security, deps
    /models       — SQLAlchemy модели
    /schemas      — Pydantic схемы
    /services     — бизнес-логика (queue, crm, whatsapp, notifications)
    /workers      — фоновые задачи (напоминания, статистика)
  main.py
  alembic/

/frontend
  /src
    /components
    /views
    /stores
    /api
    /composables

/admin-frontend
  /src
    (отдельное Vue-приложение для Super Admin)

## Бизнес-правила (ОБЯЗАТЕЛЬНО читай перед реализацией)

### Мультитенантность
- Каждый бизнес-клиент = tenant
- Все таблицы содержат tenant_id (UUID)
- Запросы ВСЕГДА фильтруются по tenant_id из JWT
- Никогда не возвращать данные других тенантов

### Очередь
- Единица очереди = QueueEntry (один визит клиента)
- Статусы: waiting → called → in_service → done | cancelled | no_show
- ETA считается как: (позиция_в_очереди × avg_service_time_для_этой_услуги)
- avg_service_time = скользящее среднее последних 10 завершённых визитов этой услуги
- VIP клиенты (is_vip=True) вставляются после текущего обслуживаемого, перед обычной очередью
- Позиция в очереди = Redis Sorted Set score (timestamp добавления, VIP получают score - 86400)

### Клиент
- Идентифицируется по номеру телефона (E.164 формат, например +966501234567)
- VIP = кто сделал >= 10 визитов ИЛИ помечен вручную
- Средний чек = среднее по всем завершённым визитам где amount > 0

### Языки тенанта
- Каждый тенант выбирает какие языки включены: `enabled_languages: list[str]` в таблице tenants
- Доступные языки: `ar` (арабский), `en` (английский), `ru` (русский)
- По умолчанию: `["ar", "en"]`
- Dashboard тенанта показывает переключатель только для включённых языков
- WhatsApp/Telegram бот отвечает только на включённых языках тенанта (fallback → ar)

### Мессенджеры (state machine — общая для всех каналов)
Состояния: IDLE → SELECTING_SERVICE → IN_QUEUE → BEING_SERVED → DONE
- IDLE: любое сообщение → приветствие + список услуг
- SELECTING_SERVICE: цифра или название услуги → подтверждение + позиция
- IN_QUEUE: "отмена" / "cancel" / "إلغاء" / "отмена" → отмена из очереди
- Все остальные состояния: информационные ответы
- Общая бизнес-логика в `message_handler.py`, транспорты: `whatsapp_handler.py`, `telegram_handler.py`

### WhatsApp (360dialog)
- Webhook: POST /api/v1/webhook/{secret_path}
- Клиент идентифицируется по номеру телефона (E.164)
- Настройка per-tenant: `d360_api_key`, `d360_channel_id`

### Telegram Bot
- Опциональный канал, включается per-tenant через настройки
- Настройка per-tenant: `telegram_bot_token` (каждый тенант — свой бот)
- Клиент идентифицируется по `telegram_chat_id`, привязывается к Customer через phone (запрашивается при первом контакте)
- Webhook: POST /api/v1/telegram/{tenant_id}/webhook
- Библиотека: aiogram 3.x (async)

### Уведомления
- "Скоро ваша очередь": когда до клиента остаётся 2 человека (3-я позиция)
- "Подъезжайте": когда вызван (статус called)
- Язык уведомления = язык последнего сообщения клиента, только если он в enabled_languages тенанта

### Подписки и блокировка
- Новый тенант получает 30-дневный trial
- При истечении trial → статус past_due, tenant.is_active = False → HTTP 403 на все запросы
- Разблокировка через Super Admin Panel

### Структура проекта (дополнение)
/backend/app/services/
  message_handler.py    — общая state machine (канал-независимая)
  whatsapp_handler.py   — WhatsApp транспорт (360dialog)
  telegram_handler.py   — Telegram транспорт (aiogram)
  notifications.py      — уведомления (вызывает нужный транспорт по каналу клиента)

/frontend/src/views/
  SettingsView.vue      — настройки тенанта: enabled_languages, Telegram bot token

## Соглашения по коду
- Async везде (async def, await)
- Никаких print() — только structlog
- Все эндпоинты возвращают Pydantic-схемы, не ORM-объекты напрямую
- Тесты обязательны для services/ и api/ (pytest + pytest-asyncio)
- Никаких магических строк — всё в константах или Enum
- Комментарии на английском
