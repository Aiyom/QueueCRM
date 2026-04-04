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
- Frontend: Vue 3, TypeScript, Vite, TanStack Query (@tanstack/vue-query), Pinia
- Auth: JWT (access 15min + refresh 7days, Redis whitelist для refresh tokens)
- Deploy target: Railway (backend) + Vercel (frontend)

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

### WhatsApp диалог (state machine)
Состояния: IDLE → SELECTING_SERVICE → IN_QUEUE → BEING_SERVED → DONE
- IDLE: любое сообщение → приветствие + список услуг
- SELECTING_SERVICE: цифра или название услуги → подтверждение + позиция
- IN_QUEUE: "отмена" / "cancel" / "إلغاء" → отмена из очереди
- Все остальные состояния: информационные ответы

### Уведомления
- "Скоро ваша очередь": когда до клиента остаётся 2 человека (3-я позиция)
- "Подъезжайте": когда вызван (статус called)
- Язык уведомления = язык последнего сообщения клиента (AR или EN)

### Подписки и блокировка
- Новый тенант получает 30-дневный trial
- При истечении trial → статус past_due, tenant.is_active = False → HTTP 403 на все запросы
- Разблокировка через Super Admin Panel

## Соглашения по коду
- Async везде (async def, await)
- Никаких print() — только structlog
- Все эндпоинты возвращают Pydantic-схемы, не ORM-объекты напрямую
- Тесты обязательны для services/ и api/ (pytest + pytest-asyncio)
- Никаких магических строк — всё в константах или Enum
- Комментарии на английском
