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
- Telegram: httpx (без aiogram) — опциональный канал, включается per-tenant
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

### Мессенджеры (state machine)
Состояния WhatsApp: IDLE → SELECTING_SERVICE → IN_QUEUE → BEING_SERVED → DONE
Состояния Telegram: + SELECTING_LANGUAGE (первый контакт / /start)

**Telegram первый контакт:**
- /start или первое сообщение → показать кнопки выбора языка (из enabled_languages)
- После выбора языка → запросить номер телефона (если новый) → показать услуги
- Язык сохраняется в session.context["language"], используется для всех последующих сообщений

**Telegram UI:**
- Услуги = inline keyboard (одна кнопка на строку, callback_data = UUID услуги)
- Кнопка "Cancel ❌" показывается когда клиент в очереди
- callback_query обрабатывается отдельно от text messages
- answer_callback_query вызывается для снятия спиннера

**WhatsApp UI:**
- Услуги = interactive list message (360dialog format)
- list_reply и button_reply обрабатываются в webhook, id = UUID услуги

### WhatsApp (360dialog)
- Webhook: POST /api/v1/webhook/{secret_path}/{channel_id}
- Клиент идентифицируется по номеру телефона (E.164)
- Настройка per-tenant: `d360_api_key`, `d360_channel_id`
- Поддерживает text и interactive (list_reply, button_reply) типы сообщений

### Telegram Bot
- Опциональный канал, включается per-tenant через настройки
- Настройка per-tenant: `telegram_bot_token` (каждый тенант — свой бот)
- Клиент идентифицируется по `telegram_chat_id`, привязывается к Customer через phone
- Webhook: POST /api/v1/telegram/{tenant_id}/webhook
- Реализация: httpx (без aiogram) — прямые вызовы Telegram Bot API
- Background task создаёт собственную DB сессию (не передаётся из request scope)
- Регистрация webhook: POST /api/v1/telegram/setup-webhook (TenantAdmin)

### Уведомления
- "Скоро ваша очередь": когда до клиента остаётся 2 человека (3-я позиция)
- "Подъезжайте": когда вызван (статус called)
- Язык уведомления = customer.preferred_language, только если он в enabled_languages тенанта

### Подписки и блокировка
- Новый тенант получает 30-дневный trial
- При истечении trial → статус past_due, tenant.is_active = False → HTTP 403 на все запросы
- Разблокировка через Super Admin Panel

### Предварительные записи (Appointments)

#### Модели
**WorkSchedule** — рабочее расписание тенанта:
- `day_of_week: int | null` — 0=пн..6=вс, null = переопределение конкретной даты
- `specific_date: date | null` — конкретная дата (приоритет выше day_of_week)
- `is_working: bool` — false = выходной / праздник / мастер заболел
- `open_time: time`, `close_time: time`
- `max_parallel: int` — сколько клиентов можно обслуживать одновременно
- `notes: str | null` — причина изменения

Приоритет: `specific_date` > `day_of_week`.

**Appointment** — предварительная запись:
- `tenant_id, customer_id, service_id`
- `scheduled_at: datetime`
- `status: confirmed | cancelled | done | no_show`
- `reminder_sent: bool` — флаг для cron (не слать дважды)
- `notes: str | null`

#### Логика слотов
```
слоты = от open_time до close_time с шагом avg_duration_minutes услуги
свободный слот = count(appointments где overlap) < max_parallel
```

#### Автоматика (cron, каждые 5 минут)
- **Auto-enqueue**: appointments где `scheduled_at` в [now, now+5min] и status=confirmed → добавить в live-очередь
- **Reminder**: appointments где `scheduled_at` в [now+55min, now+65min] и `reminder_sent=false` → уведомить клиента через бот → `reminder_sent=true`

#### Флоу бота (Telegram + WhatsApp)
Главное меню (IDLE после выбора языка):
- Кнопка "Живая очередь" → текущий флоу
- Кнопка "Записаться заранее" → BOOKING_DATE

```
BOOKING_DATE   → кнопки: ближайшие 7 рабочих дней
BOOKING_SERVICE → кнопки: услуги
BOOKING_TIME   → кнопки: доступные слоты (только свободные)
               → если нет мест: "нет мест, выберите другой день"
BOOKING_DONE   → "✅ Запись подтверждена: 10 апр, 10:00, Oil Change"
               → уведомление менеджеру
               → кнопка "Мои записи" | "Отменить"

MY_APPOINTMENTS → список предстоящих записей с кнопками "Отменить"
               → отмена доступна если до визита > 2 часов
```

#### API
```
GET  /appointments/slots?date=2026-04-10&service_id=xxx   → свободные слоты
GET  /appointments/?date=2026-04-10&status=confirmed      → список для менеджера
POST /appointments/                                        → создать из дашборда
PATCH /appointments/{id}/cancel
GET  /work-schedule/
PUT  /work-schedule/                                       → сохранить недельное расписание
POST /work-schedule/override                               → переопределить конкретную дату
```

#### Вид менеджера (AppointmentsView.vue)
- Переключатель: **День** / **Неделя** / **Список**
- День: вертикальная сетка по часам, параллельные записи рядом
- Неделя: 7 колонок, компактные карточки
- Список: таблица с фильтром по дате — удобен на мобильном
- Новая запись через модал прямо из дашборда

### Структура проекта (актуальная)
/backend/app/services/
  bot_service.py          — WhatsApp state machine
  telegram_bot_service.py — Telegram state machine (с inline кнопками)
  whatsapp_service.py     — WhatsApp транспорт (360dialog), включая interactive list
  telegram_service.py     — Telegram транспорт (httpx → Bot API)
  queue_service.py        — бизнес-логика очереди
  appointment_service.py  — предварительные записи (slots, booking, auto-enqueue)
  notifications.py        — уведомления

/backend/app/models/
  tenant.py               — enabled_languages (ARRAY), telegram_bot_token
  customer.py             — telegram_chat_id
  telegram_session.py     — сессии Telegram бота
  work_schedule.py        — рабочее расписание (НОВОЕ)
  appointment.py          — предварительные записи (НОВОЕ)

/frontend/src/views/
  SettingsView.vue        — языки, WhatsApp, Telegram
  AppointmentsView.vue    — управление записями, день/неделя/список (НОВОЕ)
  ScheduleView.vue        — настройка рабочего расписания (НОВОЕ)

## Соглашения по коду
- Async везде (async def, await)
- Никаких print() — только structlog
- Все эндпоинты возвращают Pydantic-схемы, не ORM-объекты напрямую
- Тесты обязательны для services/ и api/ (pytest + pytest-asyncio)
- Никаких магических строк — всё в константах или Enum
- Комментарии на английском
