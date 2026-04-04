# Claude Code — Промпты для QueueCRM KSA

## Как использовать этот файл
Каждый промпт — одна сессия Claude Code. Не смешивай задачи.
Порядок важен: каждый модуль зависит от предыдущего.

## Карта сессий

| # | Сессия | Что строим | Кто использует |
|---|---|---|---|
| 0 | CLAUDE.md | Контекст проекта | Claude Code |
| 0.5 | GitHub + структура | Репо, папки, первый коммит | — |
| 1 | База данных | Модели, миграции, инфра | — |
| 2 | Auth | JWT, мультитенантность | Все роли |
| 3 | Queue Engine | Очередь, ETA, WebSocket | Операторы + клиенты |
| 4 | WhatsApp Bot | State machine, уведомления | Клиенты |
| 5 | CRM + Аналитика | Клиенты, сегменты, статистика | Менеджеры |
| 6 | Dashboard (фронт) | Операционный дашборд | Операторы + менеджеры |
| 7 | QR + Публичная страница | Вход для клиентов | Клиенты (мобильный) |
| 8 | Seed + Деплой | Начальные данные, Railway/Vercel | DevOps |
| 9 | Super Admin Panel | Управление тенантами, MRR | Ты как SaaS-владелец |
| 10 | i18n Admin Panel | RU язык для админки | Ты + RU команда |
| 11 | Маркетинговый сайт | Лендинг AR/EN/RU + тарифы | Потенциальные клиенты |
| 12 | Деплой на Render + Upstash | Бесплатный хостинг для демо | DevOps |

---

## ШАГ 0 — Создай CLAUDE.md (делается один раз)

Создай файл `CLAUDE.md` в корне проекта и вставь туда:

```markdown
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
- Auth: JWT (access 15min + refresh 7days)
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
- "Скоро ваша очередь": когда до клиента остаётся 2 человека
- "Подъезжайте": когда вызван (статус called)
- Язык уведомления = язык последнего сообщения клиента (AR или EN)

## Соглашения по коду
- Async везде (async def, await)
- Никаких print() — только structlog
- Все эндпоинты возвращают Pydantic-схемы, не ORM-объекты напрямую
- Тесты обязательны для services/ и api/ (pytest + pytest-asyncio)
- Никаких магических строк — всё в константах или Enum
- Комментарии на английском
```

---

## ШАГ 0.5 — GitHub: подключи репо и сделай первый коммит

Это делается один раз до всех сессий. Не через Claude Code — руками в терминале.

```
Репо: https://github.com/Aiyom/QueueCRM.git
```

**1. Если проект ещё не создан локально — создай папку:**

mkdir QueueCRM
cd QueueCRM

**2. Инициализируй git и подключи репо:**

git init
git remote add origin https://github.com/Aiyom/QueueCRM.git

**3. Положи промпт файл в папку docs/:**

mkdir docs
# Скопируй CLAUDE_CODE_PROMPTS.md в docs/

**4. Создай .gitignore в корне проекта:**

.env
.env.*
!.env.example
__pycache__/
*.pyc
*.pyo
node_modules/
dist/
.venv/
venv/
*.egg-info/
.DS_Store
slide-*.jpg
*.pdf
build_pptx.js

**5. Первый коммит:**

git add .
git commit -m "initial: project structure + Claude Code prompts"
git push -u origin main

**6. Дай Render доступ к репо (один раз, перед Сессией 12):**

Render.com → Dashboard → Account Settings
→ GitHub → Install Render app
→ Выбери Only selected repositories → QueueCRM → Save

**После каждой сессии делай коммит:**

git add .
git commit -m "session N: что сделано"
git push

---

## СЕССИЯ 1 — Структура проекта + база данных

```
Создай структуру проекта QueueCRM согласно CLAUDE.md.

Задача: только инфраструктура и модели БД. Никакой бизнес-логики.

Сделай следующее:

1. Создай структуру папок согласно CLAUDE.md

2. backend/app/core/config.py
   - Pydantic BaseSettings
   - Поля:
     DATABASE_URL, REDIS_URL,
     JWT_SECRET_KEY, JWT_ALGORITHM="HS256",
     ACCESS_TOKEN_EXPIRE_MINUTES=15, REFRESH_TOKEN_EXPIRE_DAYS=7,
     D360_API_URL="https://waba.360dialog.io/v1", D360_PARTNER_TOKEN,
     WEBHOOK_SECRET_PATH,        — глобальный случайный hex, один на всё приложение
     PUBLIC_APP_URL,             — базовый URL публичной страницы (например https://qcrm.app)
     ALLOWED_ORIGINS             — CORS origins через запятую
   - Читается из .env файла

3. backend/app/models/ — SQLAlchemy 2.0 async модели (ВСЕ модели здесь, одна миграция):

   Tenant (бизнес-клиент системы):
   - id: UUID pk
   - name: str
   - phone: str (основной WhatsApp номер бизнеса)
   - slug: str unique (для QR-ссылок, например "wash-king-riyadh")
   - is_active: bool default True
   - is_accepting_queue: bool default True  — закрыть/открыть приём (используется в Сессии 7)
   - d360_api_key: str nullable            — API-ключ канала 360dialog (Сессия 4)
   - d360_channel_id: str nullable         — ID канала 360dialog для идентификации webhook (Сессия 4)
   - created_at, updated_at

   Service (услуга тенанта):
   - id: UUID pk
   - tenant_id: FK Tenant
   - name_ar: str (название по-арабски)
   - name_en: str
   - avg_duration_minutes: int default 30 (пересчитывается автоматически)
   - is_active: bool default True
   - sort_order: int default 0

   Customer (клиент бизнеса):
   - id: UUID pk
   - tenant_id: FK Tenant
   - phone: str (E.164, например +966501234567)
   - name: str nullable
   - notes: str nullable                   — внутренние заметки оператора
   - is_vip: bool default False
   - vip_set_manually: bool default False (если True — не пересчитывать автоматически)
   - total_visits: int default 0
   - total_spent: Numeric(10,2) default 0
   - preferred_language: str default "ar" (ar или en)
   - last_seen_at: datetime nullable
   - created_at, updated_at
   - UNIQUE constraint: (tenant_id, phone)

   QueueEntry (запись в очереди):
   - id: UUID pk
   - tenant_id: FK Tenant
   - customer_id: FK Customer
   - service_id: FK Service
   - status: Enum('waiting','called','in_service','done','cancelled','no_show')
   - position: int nullable (вычисляется динамически из Redis, не хранится постоянно)
   - called_at: datetime nullable
   - started_at: datetime nullable
   - finished_at: datetime nullable
   - amount: Numeric(10,2) nullable (заполняется при завершении)
   - notes: str nullable
   - created_at, updated_at

   WhatsAppSession (состояние диалога клиента):
   - id: UUID pk
   - tenant_id: FK Tenant
   - customer_id: FK Customer
   - state: Enum('idle','selecting_service','in_queue','being_served','done')
   - context: JSONB default {} (временные данные диалога)
   - expires_at: datetime (24 часа от последнего сообщения)
   - updated_at

   StaffUser (сотрудник тенанта):
   - id: UUID pk
   - tenant_id: FK Tenant
   - email: str unique
   - hashed_password: str
   - full_name: str
   - role: Enum('admin','operator') default 'operator'
   - is_active: bool default True
   - created_at

   SuperAdmin (владелец платформы — используется в Сессии 9):
   - id: UUID pk
   - email: str unique
   - hashed_password: str
   - full_name: str
   - is_active: bool default True
   - created_at, updated_at

   TenantSubscription (подписка тенанта — используется в Сессиях 4 и 9):
   - id: UUID pk
   - tenant_id: FK Tenant, unique
   - plan: Enum('starter','pro','business','enterprise') default 'starter'
   - status: Enum('trial','active','past_due','cancelled') default 'trial'
   - trial_ends_at: datetime (default: created_at + 30 дней)
   - current_period_start: datetime nullable
   - current_period_end: datetime nullable
   - monthly_price_usd: Numeric(8,2) nullable
   - notes: str nullable
   - created_at, updated_at

4. Alembic:
   - Настрой alembic.ini и env.py для async PostgreSQL
   - Создай ОДНУ начальную миграцию со всеми моделями выше
   - Не создавай отдельные миграции для полей — всё сразу в одной

5. backend/app/core/database.py
   - AsyncEngine, AsyncSession, get_db dependency для FastAPI

6. backend/app/main.py
   - Базовый FastAPI app
   - CORS (разрешить localhost:5173 и продакшн-домен из env)
   - Health check GET /health → {"status": "ok", "version": "0.1.0"}
   - Подключение роутеров (пока пустые плейсхолдеры)

7. docker-compose.yml для локальной разработки:
   - postgres:16
   - redis:7-alpine
   - Не включай сам app — разработчик запускает его локально

8. .env.example с документированными переменными

9. requirements.txt с версиями:
   fastapi, uvicorn[standard], sqlalchemy[asyncio], asyncpg,
   alembic, redis[hiredis], pydantic-settings, python-jose[cryptography],
   passlib[bcrypt], structlog, httpx, apscheduler,
   qrcode[pil],
   pytest, pytest-asyncio

Чего НЕ делать:
- Не создавай роутеры с реальной логикой — только заглушки
- Не добавляй бизнес-логику в модели
- Не создавай frontend пока
- Не добавляй ничего кроме того, что описано выше
```

---

## СЕССИЯ 2 — Аутентификация + мультитенантность

```
Реализуй систему аутентификации для QueueCRM. Читай CLAUDE.md.

Контекст: модели уже созданы (StaffUser, Tenant). Нужна auth система.

1. backend/app/core/security.py
   - create_access_token(data: dict, expires_delta) → str
     JWT claims: {"sub": str(user_id), "tenant_id": str(tenant_id), "role": role}
   - create_refresh_token(data: dict) → str
     JWT claims: {"sub": str(user_id), "jti": str(uuid4())} — jti уникальный ID токена
   - verify_token(token: str) → dict | None
   - get_password_hash(password: str) → str
   - verify_password(plain: str, hashed: str) → bool
   - Используй python-jose и passlib

   Refresh token whitelist (Redis):
   - save_refresh_token(jti: str, user_id: UUID, redis) → None:
     await redis.setex(f"refresh:{jti}", 7*24*3600, str(user_id))
   - is_refresh_token_valid(jti: str, redis) → bool:
     return await redis.exists(f"refresh:{jti}")
   - renew_refresh_token_ttl(jti: str, redis) → None:
     await redis.expire(f"refresh:{jti}", 7*24*3600)
     (вызывается при каждом успешном /refresh — активный пользователь не теряет сессию)
   - revoke_refresh_token(jti: str, redis) → None:
     await redis.delete(f"refresh:{jti}")

2. backend/app/core/deps.py — FastAPI dependencies:
   - get_redis() → Redis: возвращает Redis клиент (используется во всех эндпоинтах с auth)
   - get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db), redis: Redis = Depends(get_redis)) → StaffUser
     Декодирует JWT, находит пользователя, проверяет is_active=True
     Raises HTTP 401 если токен невалиден или пользователь не найден
   - get_current_tenant(current_user: StaffUser = Depends(get_current_user)) → Tenant
     Возвращает tenant текущего пользователя
     Raises HTTP 403 если tenant.is_active=False
   - require_admin(current_user: StaffUser = Depends(get_current_user)) → StaffUser
     Проверяет role == 'admin', иначе HTTP 403

3. backend/app/api/auth.py — роутер /api/v1/auth:
   POST /login
   - Body: {email: str, password: str}
   - Response: {access_token: str, refresh_token: str, token_type: "bearer", user: UserSchema}
   - Ищет пользователя по email в рамках активных тенантов
   - Проверяет пароль
   - HTTP 401 с сообщением "Invalid credentials" (одно и то же для неверного email И пароля)
   - Генерирует refresh token с уникальным jti
   - Сохраняет jti в Redis: save_refresh_token(jti, user_id, redis)

   POST /refresh
   - Body: {refresh_token: str}
   - Response: {access_token: str, token_type: "bearer"}
   - Декодирует refresh token, извлекает jti
   - Проверяет: is_refresh_token_valid(jti, redis) → если False → HTTP 401
   - Обновляет TTL в Redis: redis.expire(f"refresh:{jti}", 7*24*3600)
     (чтобы активный пользователь не был выкинут через 7 дней с момента логина)
   - Выдаёт новый access token
   - Refresh token НЕ меняется (jti остаётся тем же до logout)

   POST /logout
   - НЕ требует валидный access token (Depends не нужен — пользователь может разлогиниться с просроченным токеном)
   - Body: {refresh_token: str}
   - Декодирует refresh_token БЕЗ проверки expiry (verify_exp=False) — только извлекает jti
   - Вызывает revoke_refresh_token(jti, redis) — удаляет из Redis
   - Если jti не найден в Redis — всё равно возвращает 200 (идемпотентно)
   - Response: {"message": "logged out"}

   GET /me
   - Depends: get_current_user
   - Response: UserSchema (без пароля)

4. Pydantic схемы (backend/app/schemas/auth.py):
   - LoginRequest, TokenResponse, UserSchema (id, email, full_name, role, tenant_id)
   - LogoutRequest: {refresh_token: str}

5. Тесты backend/tests/test_auth.py:
   - test_login_success
   - test_login_wrong_password → 401
   - test_login_wrong_email → 401 (такое же сообщение как неверный пароль)
   - test_refresh_token_valid
   - test_refresh_token_after_logout → 401 (jti удалён из Redis)
   - test_logout_invalidates_token
   - test_new_login_after_logout_works (новый jti, новый токен)
   - test_get_me_authenticated
   - test_get_me_unauthenticated → 401
   - test_tenant_isolation: создай двух тенантов, убедись что токен тенанта А не даёт доступ к данным тенанта Б
   Используй pytest-asyncio, httpx AsyncClient, фикстуры с тестовой БД

Чего НЕ делать:
- Не добавляй регистрацию через API (тенанты создаются через admin CLI или seed)
- Не добавляй OAuth / social login
- Не храни refresh токены в PostgreSQL — только Redis whitelist
- Не создавай endpoint смены пароля (MVP)
```

---

## СЕССИЯ 3 — Queue Engine (ядро системы)

```
Реализуй Queue Engine — самый важный модуль системы. Читай CLAUDE.md внимательно.

Контекст: модели БД готовы. Auth готов. Это сердце продукта.

1. backend/app/services/queue_service.py — класс QueueService:

   Инициализация: принимает AsyncSession + Redis client

   async def restore_queue_from_db(tenant_id):
   - Вызывается при старте приложения для каждого активного тенанта
   - Находит все QueueEntry со статусами 'waiting' и 'called' в PostgreSQL
   - Проверяет, есть ли уже данные в Redis Sorted Set f"queue:{tenant_id}"
     Если Redis НЕ пуст — пропускает (рестарт без потери Redis, например rolling restart)
     Если Redis пуст — восстанавливает:
       * VIP клиент: score = created_at.timestamp() - 86400
       * Обычный клиент: score = created_at.timestamp()
     Порядок сохраняется через оригинальный created_at из БД
   - Логирует: сколько записей восстановлено

   В backend/app/main.py добавь lifespan event:
   @asynccontextmanager
   async def lifespan(app):
       async with AsyncSession(engine) as session:
           redis = await get_redis_client()
           service = QueueService(session, redis)
           tenants = await session.execute(select(Tenant).where(Tenant.is_active == True))
           for tenant in tenants.scalars():
               await service.restore_queue_from_db(tenant.id)
       yield

   async def add_to_queue(tenant_id, customer_id, service_id) → QueueEntry:
   - Проверяет, нет ли уже активной записи этого клиента у этого тенанта
     (статусы waiting или called). Если есть → raise ValueError("Customer already in queue")
   - Создаёт QueueEntry со статусом 'waiting'
   - Добавляет в Redis Sorted Set с ключом f"queue:{tenant_id}"
     Обычный клиент: score = time.time()
     VIP клиент: score = time.time() - 86400
     (VIP всегда имеет меньший score → всегда впереди обычных клиентов)
     Пример: очередь [A(обычный), B(обычный)], приходит VIP →
             [VIP, A, B] — VIP на позиции 1 в ожидании
             Текущий обслуживаемый уже вышел из Redis через ZPOPMIN, он не мешает
     member = str(queue_entry.id)
   - Публикует событие в Redis channel f"queue_updates:{tenant_id}"
     payload: {"event": "added", "entry_id": str(id), "position": position}
   - Возвращает QueueEntry с вычисленным полем position

   async def get_position(tenant_id, queue_entry_id) → int:
   - ZRANK в Redis Sorted Set f"queue:{tenant_id}"
   - Возвращает позицию + 1 (1-based)
   - Если не найден → raise ValueError("Entry not found in queue")

   async def get_eta_minutes(tenant_id, queue_entry_id, service_id) → int:
   - Получает позицию через get_position
   - Берёт avg_duration_minutes из Service
   - ETA = (position - 1) * avg_duration_minutes
   - Минимум 0

   async def call_next(tenant_id, staff_user_id) → QueueEntry | None:
   - Берёт первый элемент из Redis Sorted Set (ZPOPMIN)
   - Если очередь пуста → возвращает None
   - Обновляет статус QueueEntry на 'called', called_at = now()
   - Публикует событие {"event": "called", "entry_id": str(id), "tenant_id": str(tenant_id), "customer_id": str(customer_id), "customer_phone": phone}
   - Возвращает QueueEntry

   async def start_service(tenant_id, queue_entry_id) → QueueEntry:
   - Находит QueueEntry, проверяет статус == 'called'
   - Меняет на 'in_service', started_at = now()
   - Публикует {"event": "started", "entry_id": str(id)}

   async def finish_service(tenant_id, queue_entry_id, amount: Decimal | None) → QueueEntry:
   - Находит QueueEntry, проверяет статус == 'in_service'
   - Меняет на 'done', finished_at = now(), amount = amount
   - Пересчитывает avg_duration_minutes для Service:
     Берёт последние 10 QueueEntry для этой service_id где:
       status = 'done' AND started_at IS NOT NULL AND finished_at IS NOT NULL
     Считает среднее (finished_at - started_at) в минутах
     Обновляет Service.avg_duration_minutes
     (no_show не учитывается — сервис не был оказан полностью)
   - Обновляет Customer: total_visits += 1, total_spent += amount (если amount > 0)
   - Автоматически проставляет is_vip = True если total_visits >= 10 и не vip_set_manually
   - Публикует {"event": "finished", "entry_id": str(id)}

   async def cancel(tenant_id, queue_entry_id, reason: str = "customer_request") → QueueEntry:
   - Работает для статусов 'waiting' и 'called'
   - Убирает из Redis Sorted Set (ZREM)
   - Меняет статус на 'cancelled'
   - Публикует {"event": "cancelled", "entry_id": str(id)}

   async def mark_no_show(tenant_id, queue_entry_id) → QueueEntry:
   - Работает только для статуса 'called' (клиент был вызван, но не пришёл)
   - Меняет статус на 'no_show', finished_at = now()
   - Публикует {"event": "no_show", "entry_id": str(id)}

   async def get_queue_snapshot(tenant_id) → list[QueueEntryWithDetails]:
   - Получает все entry_id из Redis Sorted Set в порядке очереди
   - Загружает из PostgreSQL с JOIN на Customer и Service
   - Возвращает с вычисленными position и eta_minutes для каждого

   async def check_and_notify_upcoming(tenant_id):
   - Смотрит на 3-ю позицию в очереди (если есть)
   - Если у этого клиента ещё не было отправлено уведомление "upcoming"
     (проверяй флаг в Redis f"notified:upcoming:{entry_id}", TTL 1 час)
   - Публикует событие {"event": "notify_upcoming", "tenant_id": str(tenant_id), "customer_id": ..., "eta_minutes": ...}
     tenant_id обязателен — worker использует его чтобы найти d360_api_key тенанта

2. backend/app/api/queue.py — роутер /api/v1/queue:

   GET /api/v1/queue/current
   - Depends: get_current_tenant
   - Response: список QueueEntryWithDetails в порядке очереди

   POST /api/v1/queue/call-next
   - Depends: get_current_tenant
   - Вызывает queue_service.call_next()
   - Response: QueueEntry или {"message": "Queue is empty"}

   PATCH /api/v1/queue/{entry_id}/start
   PATCH /api/v1/queue/{entry_id}/finish
   - Body для finish: {amount: float | null}
   PATCH /api/v1/queue/{entry_id}/cancel
   PATCH /api/v1/queue/{entry_id}/no-show
   - Только для статуса 'called', иначе HTTP 400

   WebSocket /api/v1/queue/ws
   - Depends: get_current_tenant (через query param token=...)
   - Подписывается на Redis channel f"queue_updates:{tenant_id}"
   - Пересылает события клиенту как JSON
   - При подключении сразу отправляет текущий snapshot очереди
   - Пинг/понг каждые 30 секунд

3. Pydantic схемы (backend/app/schemas/queue.py):
   QueueEntryWithDetails включает: все поля QueueEntry + customer_name, customer_phone,
   service_name_ar, service_name_en, position, eta_minutes

4. backend/tests/test_queue_service.py:
   - test_add_to_queue_normal
   - test_add_to_queue_vip_gets_priority (VIP должен быть перед обычным)
   - test_cannot_add_twice (второй вызов raises ValueError)
   - test_call_next_returns_first
   - test_call_next_empty_queue_returns_none
   - test_finish_updates_avg_duration
   - test_finish_sets_vip_after_10_visits
   - test_cancel_removes_from_redis
   - test_no_show_only_works_for_called_status
   - test_eta_calculation
   - test_restore_queue_from_db_restores_correct_order
   - test_restore_queue_skips_if_redis_not_empty

Чего НЕ делать:
- Не реализуй WebSocket-клиент на фронтенде в этой сессии
- Не добавляй бронирование слотов (appointments) — это отдельный модуль
- Не трогай WhatsApp интеграцию
- Не добавляй логику уведомлений — только публикуй события
```

---

## СЕССИЯ 4 — WhatsApp Bot (state machine)

```
Реализуй WhatsApp-бота для QueueCRM. Читай CLAUDE.md — особенно раздел state machine.

Контекст: Queue Engine готов. Модели готовы.

1. backend/app/services/whatsapp_service.py — класс WhatsAppService:

   Инициализация: принимает d360_api_key тенанта (у каждого тенанта свой ключ канала 360dialog)

   async def send_message(to_phone: str, text: str):
   - POST на 360dialog API: {settings.D360_API_URL}/messages
   - Header: D360-API-KEY: {d360_api_key}
   - Body: {"to": phone, "type": "text", "text": {"body": text}}
   - Логирует ошибки, не падает (try/except с логом)

   async def send_list_message(to_phone: str, header: str, body: str, button_text: str, sections: list):
   - Отправляет интерактивное сообщение с кнопками выбора услуги
   - Body: {"to": phone, "type": "interactive", "interactive": {формат 360dialog list message}}

   async def parse_incoming(payload: dict) → IncomingMessage | None:
   - Парсит webhook payload от 360dialog (формат аналогичен Meta Cloud API)
   - Возвращает IncomingMessage(phone, text, message_id, timestamp) или None если не текстовое

2. backend/app/services/bot_service.py — класс BotService:

   Инициализация: AsyncSession, WhatsAppService, QueueService

   async def handle_message(tenant_id: UUID, phone: str, text: str, message_id: str):
   - Находит или создаёт Customer по (tenant_id, phone)
   - Обновляет Customer.last_seen_at = now()
   - Определяет язык: если text содержит арабские символы → 'ar', иначе 'en'
   - Обновляет Customer.preferred_language
   - Находит или создаёт WhatsAppSession
   - Если сессия истекла (expires_at < now()) → сбрасывает state на 'idle'
   - Роутит на обработчик по текущему state
   - Обновляет expires_at = now() + 24h

   async def _handle_idle(session, customer, text) → str:
   - Любой текст → приветствие + список услуг
   - Меняет state на 'selecting_service'
   - Сохраняет available_services в session.context
   - Возвращает текст ответа на языке клиента

   Тексты на AR:
   "مرحباً {name}! 👋\nاختر الخدمة المطلوبة:\n{список_услуг}"
   Тексты на EN:
   "Hello {name}! 👋\nPlease select a service:\n{список_услуг}"
   (name = Customer.name если есть, иначе пустая строка)

   async def _handle_selecting_service(session, customer, text) → str:
   - Парсит текст по приоритету:
     1. Цифра (1, 2, 3...) → берёт услугу по порядковому номеру из списка
     2. Точное совпадение (case-insensitive) с name_ar или name_en
     3. Substring совпадение (case-insensitive) с name_ar или name_en — берёт первое
     Никаких сторонних библиотек (Levenshtein и т.д.) — только строковые операции
   - Если не распознал → повторяет список услуг с сообщением об ошибке
   - Если распознал → вызывает queue_service.add_to_queue()
   - Меняет state на 'in_queue'
   - Сохраняет queue_entry_id в session.context
   - Возвращает подтверждение с позицией и ETA

   Текст подтверждения AR:
   "✅ تم إضافتك للقائمة!\n📍 موقعك: {position}\n⏱ الوقت المتوقع: {eta} دقيقة\nللإلغاء، أرسل: إلغاء"
   Текст EN:
   "✅ You're in the queue!\n📍 Position: {position}\n⏱ Estimated wait: {eta} min\nTo cancel, send: cancel"

   async def _handle_in_queue(session, customer, text) → str:
   - Если text.lower() in ['cancel', 'إلغاء', 'الغاء'] → отменяет
   - Иначе → статус в очереди (позиция + ETA)

   async def _handle_being_served(session, customer, text) → str:
   - "Вас сейчас обслуживают. Пожалуйста, ожидайте."

   async def _handle_done(session, customer, text) → str:
   - Сбрасывает state на 'idle'
   - Вызывает _handle_idle для нового диалога

   async def notify_upcoming(customer_id: UUID, eta_minutes: int):
   - Отправляет уведомление "скоро ваша очередь"
   - AR: "⏰ دورك قريباً! الوقت المتوقع: {eta} دقيقة. يرجى التوجه إلى الخدمة."
   - EN: "⏰ Your turn is coming up! About {eta} min. Please head to the service."

   async def notify_called(customer_id: UUID):
   - AR: "🔔 حان دورك الآن! يرجى التوجه إلى الكاونتر."
   - EN: "🔔 It's your turn now! Please proceed to the counter."

3. backend/app/api/webhooks.py — роутер /api/v1/webhooks:

   GET /api/v1/webhooks/whatsapp
   - 360dialog не использует hub.verify_token challenge как Meta
   - Эндпоинт просто возвращает HTTP 200 (нужен при первичной настройке webhook URL в 360dialog Hub)

   POST /api/v1/webhooks/whatsapp
   - Принимает webhook payload от 360dialog
   - URL: /api/v1/webhooks/whatsapp/{WEBHOOK_SECRET_PATH}
     WEBHOOK_SECRET_PATH — глобальный случайный hex из env (один на всё приложение)
     HTTP 403 если path не совпадает с env переменной
   - Тенант определяется по d360_channel_id внутри payload
     (каждый тенант имеет уникальный d360_channel_id — ищи в БД по этому полю)
     HTTP 200 если тенант не найден — не раскрывать что канал неизвестен
   - Вызывает bot_service.handle_message() в фоне (BackgroundTasks)
   - ВСЕГДА возвращает HTTP 200 {"status": "ok"} немедленно
     (360dialog тоже повторяет при отсутствии ответа)

4. backend/app/workers/notification_worker.py:
   - Запускается каждые 30 секунд (asyncio loop или APScheduler)
   - Для каждого активного тенанта вызывает queue_service.check_and_notify_upcoming()
   - Слушает Redis channel queue_updates:* на события notify_upcoming и called
   - Вызывает bot_service.notify_upcoming() и bot_service.notify_called()

   Дополнительная задача — проверка истечения триала (запускается раз в час):
   - Находит все TenantSubscription где status='trial' AND trial_ends_at < now()
   - Меняет status → 'past_due', tenant.is_active → False
   - Логирует: какой тенант заблокирован и когда
   - Тенант с is_active=False получает HTTP 403 на все запросы (уже проверяется в get_current_tenant)

5. Поля d360_api_key и d360_channel_id уже есть в Tenant (созданы в Сессии 1) — используй их.

6. Тесты backend/tests/test_bot_service.py:
   - test_idle_state_returns_service_list
   - test_selecting_service_by_number
   - test_selecting_service_invalid_input
   - test_cancel_from_queue_arabic
   - test_cancel_from_queue_english
   - test_language_detection_arabic
   - test_expired_session_resets_to_idle
   - test_webhook_valid_secret_path_returns_200
   - test_webhook_invalid_secret_path_returns_403
   Мокай WhatsAppService и QueueService

Чего НЕ делать:
- Не используй сторонние NLP библиотеки для парсинга — только простое сравнение строк
- Не добавляй AI/LLM в бота (это v2)
- Не реализуй голосовые сообщения
- Не добавляй медиа-сообщения (фото, документы)
- Не обрабатывай групповые сообщения WhatsApp
```

---

## СЕССИЯ 5 — CRM модуль

```
Реализуй CRM модуль для QueueCRM. Читай CLAUDE.md.

Контекст: очередь работает, WhatsApp-бот создаёт клиентов. Теперь управление клиентами.

1. backend/app/services/crm_service.py — класс CRMService:

   async def get_customer(tenant_id, customer_id) → CustomerDetail
   async def get_or_create_customer(tenant_id, phone) → Customer (используется ботом)
   async def update_customer(tenant_id, customer_id, data: CustomerUpdateSchema) → Customer
   async def set_vip(tenant_id, customer_id, is_vip: bool) → Customer:
   - Устанавливает is_vip и vip_set_manually = True
   - Если is_vip=False и vip_set_manually=True → сбрасывает оба флага

   async def get_customer_visits(tenant_id, customer_id, limit=20, offset=0) → list[QueueEntry]
   async def search_customers(tenant_id, query: str, segment: str | None) → list[Customer]:
   - Поиск по phone (частичное совпадение) и name
   - Фильтр по segment: 'vip', 'frequent' (>= 5 визитов), 'inactive' (не было > 30 дней)

   async def get_segments_stats(tenant_id) → dict:
   - Returns: {total, vip_count, frequent_count, new_count (первый визит < 7 дней), inactive_count}

2. backend/app/api/customers.py — роутер /api/v1/customers:

   GET /api/v1/customers
   - Query: search (str), segment (str), limit (int, max 100), offset (int)
   - Depends: get_current_tenant

   GET /api/v1/customers/{customer_id}
   - Возвращает CustomerDetail (с последними 5 визитами)

   PATCH /api/v1/customers/{customer_id}
   - Обновляемые поля: name, is_vip, notes (поле уже есть в модели Customer из Сессии 1)

   GET /api/v1/customers/{customer_id}/visits
   - Query: limit, offset
   - Возвращает историю визитов с деталями

   GET /api/v1/customers/segments/stats
   - Статистика по сегментам для дашборда
   - ВАЖНО: путь /segments/stats, не /stats/segments — иначе FastAPI спутает с /customers/{customer_id}

3. Pydantic схемы (backend/app/schemas/customer.py):
   CustomerDetail: все поля Customer + visits_last_5 + avg_visit_interval_days + predicted_next_visit

   avg_visit_interval_days: среднее кол-во дней между визитами (если >= 2 визита)
   predicted_next_visit: last_seen_at + avg_visit_interval_days (если есть данные)

4. backend/app/services/analytics_service.py — класс AnalyticsService:

   async def get_dashboard_stats(tenant_id, date_from, date_to) → DashboardStats:
   - total_customers_served: кол-во done за период
   - total_revenue: сумма amount за период
   - avg_wait_time_minutes: среднее (called_at - created_at) в минутах
   - avg_service_time_minutes: среднее (finished_at - started_at)
   - cancellation_rate: cancelled / (done + cancelled) * 100
   - peak_hours: список {hour: int, count: int} за период — топ 24 часа

   async def get_service_stats(tenant_id, date_from, date_to) → list[ServiceStats]:
   - Для каждой услуги: count, revenue, avg_duration

5. backend/app/api/analytics.py — роутер /api/v1/analytics:

   GET /api/v1/analytics/dashboard
   - Query: date_from (date), date_to (date), default последние 7 дней

   GET /api/v1/analytics/services
   - Аналогичные параметры

6. Тесты backend/tests/test_crm_service.py:
   - test_get_or_create_new_customer
   - test_get_or_create_existing_customer
   - test_set_vip_manually
   - test_auto_vip_not_overridden_when_manual
   - test_search_by_phone
   - test_segment_vip_filter
   - test_segment_inactive_filter
   - test_tenant_isolation: клиент тенанта А не виден тенанту Б через /customers

7. backend/app/api/services.py — роутер /api/v1/services (Depends: get_current_tenant):

   GET /api/v1/services
   - Возвращает все услуги тенанта (включая неактивные, отсортированные по sort_order)

   POST /api/v1/services
   - Depends: require_admin
   - Body: {name_ar, name_en, avg_duration_minutes, sort_order}
   - Создаёт услугу для текущего тенанта

   PATCH /api/v1/services/{service_id}
   - Depends: require_admin
   - Обновляемые поля: name_ar, name_en, avg_duration_minutes, sort_order, is_active

   Pydantic схемы (backend/app/schemas/service.py): ServiceSchema, ServiceCreateSchema, ServiceUpdateSchema

Чего НЕ делать:
- Не добавляй email рассылки (MVP — только WhatsApp)
- Не создавай endpoint удаления клиентов (только деактивация через notes)
- Не добавляй импорт/экспорт клиентов (это v2)
- Не реализуй loyalty points (это v2)
```

---

## СЕССИЯ 6 — Vue Dashboard (фронтенд)

```
Создай Vue дашборд для QueueCRM. Читай CLAUDE.md.

Контекст: весь backend готов. Нужен операционный дашборд для сотрудников бизнеса.

ВАЖНО: это B2B SaaS дашборд для операторов и менеджеров в Саудовской Аравии.
Интерфейс только на английском (арабский — отдельная задача v2).
Дизайн: утилитарный, информационно плотный, как операционная система.
Приоритет: функциональность и скорость, не красота.

1. Настройка frontend/:
   - Vite + Vue 3 + TypeScript (Composition API + <script setup>)
   - @tanstack/vue-query v5 для server state
   - Pinia для client state (auth)
   - Vue Router v4 с navigation guard:
     router.beforeEach → если маршрут не /login и не /q/:slug → проверяй isAuthenticated
     если не авторизован → redirect /login
   - axios для API calls (с interceptor для JWT refresh):
     Response interceptor: если 401 И не impersonate режим → пробуй refresh → fail → logout
     Если impersonate режим и 401 → просто очищай localStorage и закрывай вкладку
   - shadcn-vue компоненты (минимально — только что нужно)
   - Tailwind CSS

2. frontend/src/api/client.ts:
   - axios instance с baseURL из env
   - Request interceptor: добавляет Bearer token
   - Response interceptor: если 401 → пробует refresh token → если fail → logout

3. Страницы (Routes):

   /login — страница входа
   - Форма email + password
   - Вызывает POST /api/v1/auth/login
   - Сохраняет токены в localStorage (ключи: qcrm_access, qcrm_refresh)
   - Редирект на /queue после успеха

   /queue — ГЛАВНАЯ страница (открывается по умолчанию)
   Левая панель (30% ширины):
   - Список текущей очереди в реальном времени
   - Каждый элемент: позиция, имя клиента (или номер телефона), услуга, ETA, бадж VIP
   - Кнопка "Call Next" вверху
   - Статус: "Queue empty" если пусто
   - WebSocket подключение к /api/v1/queue/ws

   Правая панель (70% ширины):
   - Текущий обслуживаемый клиент (большая карточка)
   - Кнопки: "Start Service" / "Finish" (с полем суммы) / "No Show"
   - История последних 10 завершённых (таблица)

   /customers — список клиентов
   - Поиск по телефону и имени (debounce 300ms)
   - Фильтры: All / VIP / Frequent / Inactive
   - Таблица: телефон, имя, визиты, последний визит, средний чек, VIP бадж
   - Клик на строку → /customers/:id

   /customers/:id — карточка клиента
   - Основная информация + кнопка toggle VIP
   - История визитов (таблица с пагинацией)
   - Predicted next visit (если есть)

   /analytics — аналитика
   - Выбор периода (date range picker, default 7 дней)
   - 4 metric cards: обслужено, выручка, среднее ожидание, отмены
   - Таблица по услугам
   - Peak hours: bar chart (часы 0-23 по оси X, количество по Y)

   /services — управление услугами (только для role=admin)
   - Страница скрыта из навигации для role=operator (Vue Router guard: redirect /queue)
   - Список услуг: name_ar, name_en, avg_duration_minutes, sort_order, is_active (toggle)
   - Кнопка "Add Service" → модальное окно с полями: name_ar, name_en, avg_duration_minutes
   - Редактирование по клику на строку (те же поля)
   - Drag-and-drop для изменения sort_order НЕ нужен — просто поле ввода числа
   - Деактивация (is_active toggle), не удаление

4. Realtime queue обновления:
   - Vue composable useQueueSocket():
     - Подключается при монтировании /queue страницы (onMounted/onUnmounted)
     - Обрабатывает события: added, called, started, finished, cancelled
     - Инвалидирует @tanstack/vue-query cache для queue
     - Показывает toast уведомление для события 'called' (имя клиента)
   - Reconnect логика: если соединение разорвано → retry каждые 5 секунд

5. frontend/src/stores/auth.ts (Pinia):
   - state: user, isAuthenticated, isImpersonating (bool), impersonatedTenantName (str)
   - actions: login(tokens, user), logout():
     1. Вызывает POST /api/v1/auth/logout с refresh_token из localStorage
     2. Очищает localStorage (qcrm_access, qcrm_refresh)
     3. Редирект на /login
     (если API вернул ошибку — всё равно очищать localStorage и редиректить)
   - Инициализируется из localStorage при старте

6. frontend/src/App.vue — обработка impersonate режима:
   При монтировании проверяй query param ?impersonate=TOKEN:
   - Если есть → сохраняй TOKEN как qcrm_access в localStorage (временный токен на 1 час)
   - Вызови GET /api/v1/auth/me чтобы получить данные пользователя
   - Установи isImpersonating=true, impersonatedTenantName из ответа
   - Удали ?impersonate из URL (history.replaceState)
   - Показывай баннер вверху страницы: "⚠️ Impersonation mode — {tenantName}"
     с кнопкой "Exit" → очищает localStorage и закрывает вкладку (window.close())
   - В impersonate режиме НЕ сохранять refresh token (токен временный, logout не нужен)

7. Обязательные UX детали:
   - Loading skeletons для всех списков (не спиннер)
   - Оптимистичные обновления: кнопка "Call Next" мгновенно убирает первый элемент из UI
   - Ошибки API: toast с текстом ошибки, не alert()
   - Все кнопки действий (Call Next, Finish) показывают loading state
   - Пустые состояния с текстом (не просто пустота)

8. frontend/.env.example:
   VITE_API_URL=http://localhost:8000
   VITE_WS_URL=ws://localhost:8000

Чего НЕ делать:
- Не делай мобильную адаптацию (MVP — только desktop)
- Не добавляй dark mode
- Не используй Vuex — только Pinia
- Не добавляй страницы настроек тенанта (MVP)
- Не добавляй drag-and-drop в очередь
- Не используй нестандартные чарт-библиотеки — только встроенные в shadcn-vue или простой SVG
```

---

## СЕССИЯ 7 — QR-код + публичная страница

```
Реализуй QR-вход для клиентов. Читай CLAUDE.md.

Контекст: весь основной функционал готов. Это точка входа для клиентов в физическом месте.

Концепция: клиент сканирует QR-код → попадает на страницу → нажимает кнопку → открывается WhatsApp с преднаписанным сообщением к боту.

1. backend/app/api/public.py — роутер /api/v1/public (без auth):

   GET /api/v1/public/tenant/{slug}
   - Возвращает публичную информацию о тенанте:
     {name, services: [{id, name_ar, name_en, avg_duration_minutes}], queue_length, is_open}
   - is_open: берётся из Tenant.is_accepting_queue (поле уже есть из Сессии 1)
   - Не возвращает внутренние данные (ID тенанта, настройки и т.д.)

   POST /api/v1/public/tenant/{slug}/check-queue
   - Body: {phone: str}
   - Возвращает статус клиента: {in_queue: bool, position: int | null, eta_minutes: int | null}
   - Для самостоятельной проверки статуса (QR на месте)

2. QR-генерация в backend:

   GET /api/v1/queue/qr-code (Depends: get_current_tenant, require_admin)
   - Генерирует QR-код как PNG
   - QR содержит URL: {settings.PUBLIC_APP_URL}/q/{tenant.slug}
   - Возвращает image/png
   - Используй библиотеку qrcode[pil]
   - Добавь qrcode[pil] в requirements.txt

3. frontend/src/views/QueueView.vue — добавь кнопку "Show QR Code":
   - Открывает модальное окно с QR-кодом (img tag с src = /api/v1/queue/qr-code)
   - Кнопка "Print" (window.print())
   - Подпись под QR: "Scan to join queue via WhatsApp"

4. frontend/src/views/public/ — публичная страница в том же Vue-приложении (не отдельный проект):

   Роут /q/:slug регистрируется в Vue Router БЕЗ auth guard и с lazy loading:
   { path: '/q/:slug', component: () => import('./views/public/QueueLanding.vue') }
   Vite автоматически выделит его в отдельный чанк — код дашборда не попадёт в бандл клиента.

   Страница /q/:slug — лэндинг для клиентов:
   - Загружает данные тенанта
   - Показывает: название бизнеса, список услуг, текущую длину очереди
   - Большая кнопка "Join Queue via WhatsApp"
     href = "https://wa.me/{tenant_whatsapp_phone}?text=Hello%20I%20want%20to%20join%20the%20queue"
     (на арабском: "مرحبا أريد الانضمام للقائمة")
   - Кнопка меняет язык (AR / EN) — переключает только UI текст
   - Если is_accepting_queue = false → показывает "Queue is closed. Please try again later."
   - Mobile-first дизайн (эта страница открывается на телефоне!)
   - Минимально: только то что нужно, никаких сложных анимаций

5. Поле is_accepting_queue уже есть в Tenant (создано в Сессии 1) — используй его.

6. Тесты backend/tests/test_public_api.py:
   - test_get_tenant_by_slug_success
   - test_get_tenant_by_slug_not_found → 404
   - test_get_tenant_returns_no_internal_data (проверь что нет tenant_id, hashed_password и т.д.)
   - test_qr_code_returns_png
   - test_check_queue_customer_in_queue
   - test_check_queue_customer_not_in_queue

Чего НЕ делать:
- Не добавляй онлайн-запись через публичную страницу (только WhatsApp)
- Не показывай номера телефонов других клиентов
- Не добавляй форму регистрации на публичной странице
- Не делай публичную страницу с авторизацией
```

---

## СЕССИЯ 8 — Seed данные + деплой конфигурация

```
Создай seed данные и конфигурацию деплоя для QueueCRM. Читай CLAUDE.md.

1. backend/scripts/seed.py — скрипт начальных данных:
   Запускается командой: python scripts/seed.py

   Создаёт трёх демо-тенантов (три вертикали бизнеса):

   ── Тенант 1: Автомойка ──
   - name: "Wash King Riyadh"
   - slug: "wash-king-riyadh"
   - phone: "+966501234567" (placeholder)
   - d360_api_key: берётся из env DEMO_D360_API_KEY
   - d360_channel_id: берётся из env DEMO_D360_CHANNEL_ID
   Услуги:
   - {name_ar: "غسيل عادي", name_en: "Basic Wash", avg_duration_minutes: 20}
   - {name_ar: "غسيل كامل", name_en: "Full Wash", avg_duration_minutes: 40}
   - {name_ar: "تلميع", name_en: "Polish", avg_duration_minutes: 60}
   - {name_ar: "تغيير زيت", name_en: "Oil Change", avg_duration_minutes: 30}
   Admin: email из env SEED_ADMIN_EMAIL_1 (default: admin@washking.sa)

   ── Тенант 2: Барбершоп ──
   - name: "Al Majd Barbershop"
   - slug: "al-majd-barbershop"
   - phone: "+966502345678" (placeholder)
   - d360_api_key, d360_channel_id: placeholder (пустые, для демо)
   Услуги:
   - {name_ar: "قص شعر", name_en: "Haircut", avg_duration_minutes: 20}
   - {name_ar: "حلاقة ذقن", name_en: "Beard Trim", avg_duration_minutes: 15}
   - {name_ar: "قص وحلاقة", name_en: "Haircut + Beard", avg_duration_minutes: 30}
   - {name_ar: "العناية بالشعر", name_en: "Hair Treatment", avg_duration_minutes: 45}
   Admin: email из env SEED_ADMIN_EMAIL_2 (default: admin@almajd.sa)

   ── Тенант 3: Женский салон ──
   - name: "Lana Beauty Salon"
   - slug: "lana-beauty"
   - phone: "+966503456789" (placeholder)
   - d360_api_key, d360_channel_id: placeholder (пустые, для демо)
   Услуги:
   - {name_ar: "قص وتصفيف", name_en: "Haircut & Style", avg_duration_minutes: 60}
   - {name_ar: "صبغ شعر", name_en: "Hair Coloring", avg_duration_minutes: 120}
   - {name_ar: "مانيكير", name_en: "Manicure", avg_duration_minutes: 45}
   - {name_ar: "بيديكير", name_en: "Pedicure", avg_duration_minutes: 45}
   - {name_ar: "عناية بالبشرة", name_en: "Facial", avg_duration_minutes: 60}
   Admin: email из env SEED_ADMIN_EMAIL_3 (default: admin@lanabeauty.sa)

   Для каждого тенанта создаёт TenantSubscription:
   - plan: 'starter', status: 'trial', trial_ends_at: now() + 30 дней

   Общий пароль для всех демо-тенантов: берётся из env SEED_ADMIN_PASSWORD

   Выводит в консоль: все созданные данные + инструкции по входу для каждого тенанта.
   Идемпотентный: если тенант с таким slug уже есть — пропускает, не падает.

2. backend/scripts/create_tenant.py — CLI для создания новых тенантов:
   Принимает аргументы: --name, --slug, --admin-email, --admin-password, --plan (default: starter)
   Используй argparse.
   Создаёт: Tenant + StaffUser(admin) + TenantSubscription(trial, 30 дней)
   Выводит: tenant_id, d360_channel_id (нужен для настройки webhook URL в 360dialog Hub)

3. railway.toml — конфигурация для Railway деплоя:
   [build]
   builder = "nixpacks"

   [deploy]
   startCommand = "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT"
   healthcheckPath = "/health"
   healthcheckTimeout = 30

4. Procfile (альтернатива для Heroku-совместимых):
   web: alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
   worker: python -m app.workers.notification_worker

5. backend/.env.production.example — все переменные для production:
   DATABASE_URL=postgresql+asyncpg://...
   REDIS_URL=redis://...
   JWT_SECRET_KEY=<generate with: openssl rand -hex 32>
   D360_API_URL=https://waba.360dialog.io/v1
   D360_PARTNER_TOKEN=<from 360dialog Partner Hub>
   WEBHOOK_SECRET_PATH=<generate with: openssl rand -hex 16>
   DEMO_D360_API_KEY=<channel api key from 360dialog Hub>
   DEMO_D360_CHANNEL_ID=<channel id from 360dialog Hub>
   ALLOWED_ORIGINS=https://your-frontend.vercel.app
   SEED_ADMIN_EMAIL_1=admin@washking.sa
   SEED_ADMIN_EMAIL_2=admin@almajd.sa
   SEED_ADMIN_EMAIL_3=admin@lanabeauty.sa
   SEED_ADMIN_PASSWORD=<strong password>

6. vercel.json для frontend:
   {
     "rewrites": [{"source": "/(.*)", "destination": "/index.html"}]
   }
   (SPA routing)

7. README.md — инструкции по локальному запуску:
   - Prerequisites
   - docker-compose up -d (postgres + redis)
   - pip install -r requirements.txt
   - alembic upgrade head
   - python scripts/seed.py
   - uvicorn app.main:app --reload
   - Отдельно: cd frontend && npm install && npm run dev
   - Как настроить 360dialog webhook URL через ngrok для локальной разработки

8. backend/tests/conftest.py — финальная версия:
   - Фикстура test_db: создаёт тестовую БД, применяет миграции, дропает после теста
   - Фикстура test_client: AsyncClient с test_db
   - Фикстура sample_tenant: создаёт тенанта + TenantSubscription (trial) в test_db
   - Фикстура sample_admin: создаёт StaffUser с role=admin для sample_tenant
   - Фикстура auth_headers: возвращает {"Authorization": "Bearer {token}"} для sample_admin
   - Фикстура sample_super_admin: создаёт SuperAdmin в test_db
   - Фикстура super_admin_headers: возвращает {"Authorization": "Bearer {token}"} для super_admin
   - Фикстура redis_client: подключается к тестовому Redis (отдельный DB номер 1)

Чего НЕ делать:
- Не хардкоди пароли и секреты в коде
- Не создавай Docker образ приложения (Railway сам билдит через nixpacks)
- Не добавляй CI/CD конфиг (GitHub Actions и т.д.) — это отдельная задача
- Не создавай Kubernetes манифесты (это MVP)
```

---

## СЕССИЯ 9 — Super Admin Panel (SaaS-владелец)

```
Реализуй Super Admin Panel для QueueCRM. Читай CLAUDE.md.

Контекст: весь продукт готов. Это панель управления для тебя как владельца SaaS —
не для клиентов системы. Отдельная auth, отдельный фронтенд, отдельный префикс API.

ВАЖНО: Super Admin — это не StaffUser. Это отдельная роль владельца платформы.
Никогда не смешивай super admin auth с tenant auth.

═══════════════════════════════════════
ЧАСТЬ A — BACKEND
═══════════════════════════════════════

1. Модели SuperAdmin и TenantSubscription уже созданы в Сессии 1 — миграция уже применена.
   Используй их напрямую из backend/app/models/.

2. backend/app/core/super_admin_deps.py — отдельные dependencies:

   get_current_super_admin(token, db) → SuperAdmin:
   - Декодирует JWT, ищет в таблице SuperAdmin (не StaffUser!)
   - Проверяет is_active=True
   - HTTP 401 если невалидно
   - Токены super admin имеют claim: {"role": "super_admin", "sub": str(id)}

   Обычный get_current_user из deps.py НЕ должен пускать super admin и наоборот.

3. backend/app/api/super_admin/ — роутер /api/v1/admin (только для super admin):

   auth.py:
   POST /api/v1/admin/auth/login
   - Body: {email, password}
   - Response: {access_token, refresh_token, token_type: "bearer"}
   - Отдельный endpoint, не путать с /api/v1/auth/login для тенантов

   POST /api/v1/admin/auth/refresh
   POST /api/v1/admin/auth/logout
   - Та же логика Redis whitelist что и для tenant auth
   GET /api/v1/admin/auth/me

   tenants.py:
   GET /api/v1/admin/tenants
   - Query: search (str), status (trial|active|past_due|cancelled), plan, limit, offset
   - Response: список тенантов с подпиской, кол-вом клиентов, кол-вом визитов за 30 дней
   - Сортировка по умолчанию: created_at DESC

   GET /api/v1/admin/tenants/{tenant_id}
   - Детальная карточка тенанта:
     - Основные данные (name, slug, phone, created_at)
     - Подписка (план, статус, даты)
     - Статистика за всё время: total_customers, total_visits, total_revenue
     - Статистика за 30 дней: visits_30d, revenue_30d, active_customers_30d
     - Последние 5 активностей (последние QueueEntry)

   POST /api/v1/admin/tenants
   - Создаёт нового тенанта + admin пользователя для него + подписку (trial)
   - Body: {name, slug, phone, admin_email, admin_password, plan}
   - Response: {tenant, staff_user, subscription}
   - После создания показывает инструкцию: настрой webhook URL в 360dialog Hub:
     {settings.PUBLIC_APP_URL}/api/v1/webhooks/whatsapp/{WEBHOOK_SECRET_PATH}
     и укажи d360_api_key / d360_channel_id тенанта через PATCH /tenants/{id}

   PATCH /api/v1/admin/tenants/{tenant_id}
   - Обновляемые поля: name, phone, is_active, is_accepting_queue, d360_api_key, d360_channel_id
   - Нельзя менять slug (это сломает QR-коды)
   - d360_api_key и d360_channel_id вводятся после получения канала в 360dialog Partner Hub

   PATCH /api/v1/admin/tenants/{tenant_id}/subscription
   - Обновляет план, статус, даты, цену
   - Body: {plan, status, monthly_price_usd, notes, trial_ends_at}
   - Если status меняется на 'active' или 'trial' → автоматически ставит tenant.is_active = True
   - Если status меняется на 'cancelled' → автоматически ставит tenant.is_active = False
   - Это главный способ разблокировать тенанта после истечения триала

   POST /api/v1/admin/tenants/{tenant_id}/subscription/extend-trial
   - Продлевает триал на N дней без смены плана
   - Body: {days: int}
   - Ставит trial_ends_at = now() + days, status = 'trial', tenant.is_active = True
   - Удобный shortcut чтобы быстро продлить не открывая форму подписки

   POST /api/v1/admin/tenants/{tenant_id}/impersonate
   - Генерирует временный access_token для admin пользователя этого тенанта
   - Токен живёт 1 час (не стандартные 15 минут)
   - Логирует: кто, когда, какой тенант (в structlog)
   - Response: {access_token, tenant_name, expires_in: 3600}
   - Используется чтобы зайти в дашборд клиента и помочь с настройкой

   stats.py:
   GET /api/v1/admin/stats/overview
   - Response:
     {
       total_tenants: int,
       active_tenants: int,          — status == 'active'
       trial_tenants: int,           — status == 'trial'
       churned_tenants: int,         — status == 'cancelled'
       mrr_usd: float,               — сумма monthly_price_usd где status == 'active'
       arr_usd: float,               — mrr * 12
       total_customers_all: int,     — всего клиентов по всем тенантам
       total_visits_30d: int,        — визиты за последние 30 дней по всем тенантам
       new_tenants_30d: int,
       churn_rate_percent: float     — churned за 30 дней / (active + churned) * 100
     }

   GET /api/v1/admin/stats/mrr-history
   - Query: months (int, default 6)
   - Response: [{month: "2024-01", mrr: 1500.00}, ...]
   - Считается как сумма monthly_price_usd активных подписок на конец каждого месяца
   - Для MVP: возвращай текущий MRR для каждого месяца (упрощённо)

   GET /api/v1/admin/stats/tenants-activity
   - Топ 10 тенантов по визитам за последние 30 дней
   - Response: [{tenant_name, visits_30d, revenue_30d, plan}]

4. backend/scripts/create_super_admin.py — CLI скрипт:
   python scripts/create_super_admin.py --email admin@qcrm.app --password ...
   Идемпотентный: если super admin с таким email уже есть — обновляет пароль.

5. Тесты backend/tests/test_super_admin.py:
   - test_super_admin_login_success
   - test_super_admin_cannot_use_tenant_token (и наоборот)
   - test_create_tenant_creates_all_entities
   - test_get_tenants_list_with_filter
   - test_patch_subscription
   - test_impersonate_generates_valid_token
   - test_impersonate_is_logged
   - test_overview_stats_mrr_calculation
   - test_expired_trial_blocks_tenant (worker меняет is_active=False)
   - test_extend_trial_reactivates_tenant
   - test_set_subscription_active_unblocks_tenant

═══════════════════════════════════════
ЧАСТЬ B — ФРОНТЕНД Super Admin
═══════════════════════════════════════

Отдельное Vue-приложение в /admin-frontend/ (не смешивать с /frontend/).
Собственный Vite проект. Деплоится отдельно на Vercel.

6. Настройка admin-frontend/:
   - Vite + Vue 3 + TypeScript (Composition API + <script setup>)
   - @tanstack/vue-query v5
   - Pinia (отдельный store, не импортировать из /frontend/)
   - Vue Router v4
   - axios с interceptor для super admin JWT
   - Tailwind CSS
   - Дизайн: тёмная тема, информационно плотный, как internal tool

7. Страницы:

   /login — вход для super admin
   - Форма email + password
   - POST /api/v1/admin/auth/login
   - Токены в localStorage: qcrm_sa_access, qcrm_sa_refresh

   /dashboard — главная страница
   Верхняя строка — 5 metric cards:
   - Total tenants
   - Active (зелёный)
   - Trial (жёлтый)
   - MRR ($)
   - Visits 30d

   Под ними два блока рядом:
   Левый (60%): таблица "Recent tenants" — последние 10, колонки:
     Name | Plan | Status | Created | Visits 30d | MRR | кнопка View
   Правый (40%): список "Top by activity" (топ 5 тенантов по визитам 30д)

   /tenants — список всех тенантов
   - Поиск по name и slug (debounce 300ms)
   - Фильтры: All / Trial / Active / Past Due / Cancelled
   - Фильтр по плану: All / Starter / Pro / Business / Enterprise
   - Таблица: Name | Slug | Plan | Status | Customers | Visits 30d | MRR | Trial ends | Actions
   - Actions: кнопка "View" + кнопка "Impersonate" (открывает дашборд тенанта в новой вкладке)
   - Кнопка "Add Tenant" вверху справа → открывает модальное окно

   Модальное окно "Add Tenant":
   - Поля: Business Name, Slug (auto-генерируется из name, редактируемое),
     Phone, Admin Email, Admin Password, Plan (select)
   - Валидация: slug только [a-z0-9-], email формат, пароль >= 8 символов
   - После создания: показывает инструкцию с кнопкой Copy:
     "Set webhook URL in 360dialog Hub to: {PUBLIC_APP_URL}/api/v1/webhooks/whatsapp/{WEBHOOK_SECRET_PATH}
      Then set d360_api_key and d360_channel_id in tenant settings."

   /tenants/:id — карточка тенанта
   Две колонки:

   Левая (40%):
   - Основная информация (name, slug, phone, created_at)
   - Поле is_active toggle (PATCH /admin/tenants/:id)
   - Поле is_accepting_queue toggle
   - Поля 360dialog: d360_channel_id (readonly), d360_api_key (masked + reveal)
     Кнопка "Edit 360dialog credentials" → открывает форму PATCH /tenants/:id
   - Кнопка "Impersonate" — большая, выделенная

   Правая (60%):
   - Карточка подписки:
     - Plan (select): Starter / Pro / Business / Enterprise
     - Status (select): Trial / Active / Past Due / Cancelled
       Если status = past_due → показывать красный баннер "⛔ Tenant is blocked"
     - Monthly price (input $)
     - Trial ends (date picker, показывается только если status=trial)
     - Notes (textarea)
     - Кнопка "Save Subscription" — сохраняет всё, автоматически разблокирует если status→active/trial
     - Кнопка "Extend Trial +7 days" (быстрое действие, POST /extend-trial с days=7)
       Показывается только если status = trial или past_due
   - Статистика (3 карточки): All-time visits | All-time revenue | Total customers
   - Последние активности (список 5 QueueEntry с датой, услугой, суммой)

   /analytics — аналитика платформы
   - MRR chart: линейный график за последние 6 месяцев
   - Tenant breakdown таблица: топ 10 по выручке за 30 дней
   - Распределение по планам: простая bar chart (Starter N, Pro N, Business N, Enterprise N)

8. Impersonate flow:
   - Кнопка "Impersonate" вызывает POST /api/v1/admin/tenants/:id/impersonate
   - Получает временный access_token тенанта
   - Открывает новую вкладку: {VITE_TENANT_DASHBOARD_URL}?impersonate={token}
   - В /frontend/ добавь обработку query param impersonate в App.vue:
     если ?impersonate=TOKEN в URL → сохраняет как временный токен + показывает
     баннер "⚠️ Impersonation mode — Tenant: {name}" с кнопкой Exit

9. admin-frontend/.env.example:
   VITE_API_URL=http://localhost:8000
   VITE_TENANT_DASHBOARD_URL=http://localhost:5173

Чего НЕ делать:
- Не смешивай /admin-frontend/ и /frontend/ — это два отдельных приложения
- Не давай super admin доступ к операционным данным напрямую (только через impersonate)
- Не добавляй биллинг/оплату (MVP — ручное управление через панель)
- Не добавляй email рассылки из панели
- Не создавай страницу логов/аудита (это v2)
- Не добавляй управление услугами тенанта из super admin (только через impersonate)
```

---

## СЕССИЯ 10 — i18n: русский язык для Admin Panel

```
Добавь поддержку русского языка в /admin-frontend/. Читай CLAUDE.md.

Контекст: Super Admin Panel на Vue 3 готова (Сессия 9).
Сейчас интерфейс только на английском. Нужно добавить RU без破坏 существующего EN.

ВАЖНО: переводить нужно только /admin-frontend/ (Super Admin Panel).
/frontend/ (дашборд тенантов) и публичная страница /q/:slug — не трогать.

═══════════════════════════════════════
ЧАСТЬ A — Настройка i18n
═══════════════════════════════════════

1. Установи vue-i18n v9:
   npm install vue-i18n@9
   Добавь в admin-frontend/package.json.

2. admin-frontend/src/i18n/index.ts:
   import { createI18n } from 'vue-i18n'
   import en from './locales/en.json'
   import ru from './locales/ru.json'

   export const i18n = createI18n({
     legacy: false,          — обязательно false (Composition API режим)
     locale: localStorage.getItem('sa_locale') || 'en',
     fallbackLocale: 'en',  — если ключ не найден в ru → берёт из en
     messages: { en, ru }
   })

3. Подключи в admin-frontend/src/main.ts:
   app.use(i18n)

4. admin-frontend/src/i18n/locales/en.json — ВСЕ строки интерфейса на EN:

   {
     "nav": {
       "dashboard": "Dashboard",
       "tenants": "Tenants",
       "analytics": "Analytics",
       "logout": "Logout"
     },
     "auth": {
       "title": "Super Admin",
       "email": "Email",
       "password": "Password",
       "login": "Sign in",
       "error": "Invalid credentials"
     },
     "dashboard": {
       "title": "Platform Overview",
       "totalTenants": "Total Tenants",
       "active": "Active",
       "trial": "Trial",
       "mrr": "MRR",
       "visits30d": "Visits (30d)",
       "recentTenants": "Recent Tenants",
       "topActivity": "Top by Activity"
     },
     "tenants": {
       "title": "Tenants",
       "search": "Search by name or slug...",
       "addTenant": "Add Tenant",
       "all": "All",
       "trial": "Trial",
       "active": "Active",
       "pastDue": "Past Due",
       "cancelled": "Cancelled",
       "cols": {
         "name": "Name",
         "slug": "Slug",
         "plan": "Plan",
         "status": "Status",
         "customers": "Customers",
         "visits30d": "Visits 30d",
         "mrr": "MRR",
         "trialEnds": "Trial Ends",
         "actions": "Actions"
       },
       "actions": {
         "view": "View",
         "impersonate": "Impersonate"
       },
       "empty": "No tenants found"
     },
     "tenantDetail": {
       "basicInfo": "Basic Information",
       "name": "Name",
       "slug": "Slug",
       "phone": "Phone",
       "created": "Created",
       "status": "Status",
       "acceptingQueue": "Accepting Queue",
       "credentials360": "360dialog Credentials",
       "channelId": "Channel ID",
       "apiKey": "API Key",
       "edit360": "Edit 360dialog credentials",
       "impersonate": "Impersonate",
       "impersonateHint": "Open tenant dashboard as admin",
       "subscription": "Subscription",
       "plan": "Plan",
       "subStatus": "Status",
       "monthlyPrice": "Monthly Price ($)",
       "trialEnds": "Trial Ends",
       "notes": "Notes",
       "saveSubscription": "Save Subscription",
       "extendTrial": "Extend Trial +7 days",
       "blockedBanner": "Tenant is blocked — past due",
       "stats": "Statistics",
       "allTimeVisits": "All-time Visits",
       "allTimeRevenue": "All-time Revenue",
       "totalCustomers": "Total Customers",
       "recentActivity": "Recent Activity"
     },
     "addTenantModal": {
       "title": "Add New Tenant",
       "businessName": "Business Name",
       "slug": "Slug",
       "slugHint": "Only lowercase letters, numbers and hyphens",
       "phone": "Phone",
       "adminEmail": "Admin Email",
       "adminPassword": "Admin Password",
       "plan": "Plan",
       "cancel": "Cancel",
       "create": "Create Tenant",
       "webhookInstructions": "Set webhook URL in 360dialog Hub to:",
       "webhookNext": "Then add d360_api_key and d360_channel_id in tenant settings."
     },
     "analytics": {
       "title": "Platform Analytics",
       "mrrHistory": "MRR History",
       "topTenants": "Top Tenants by Revenue",
       "planDistribution": "Plan Distribution",
       "months": "months"
     },
     "plans": {
       "starter": "Starter",
       "pro": "Pro",
       "business": "Business",
       "enterprise": "Enterprise"
     },
     "statuses": {
       "trial": "Trial",
       "active": "Active",
       "past_due": "Past Due",
       "cancelled": "Cancelled"
     },
     "common": {
       "save": "Save",
       "cancel": "Cancel",
       "loading": "Loading...",
       "error": "Something went wrong",
       "yes": "Yes",
       "no": "No",
       "copy": "Copy",
       "copied": "Copied!",
       "reveal": "Reveal",
       "hide": "Hide",
       "noData": "No data"
     },
     "impersonation": {
       "banner": "Impersonation mode — Tenant: {name}",
       "exit": "Exit"
     }
   }

5. admin-frontend/src/i18n/locales/ru.json — полный перевод на RU:

   {
     "nav": {
       "dashboard": "Дашборд",
       "tenants": "Клиенты",
       "analytics": "Аналитика",
       "logout": "Выйти"
     },
     "auth": {
       "title": "Супер Администратор",
       "email": "Email",
       "password": "Пароль",
       "login": "Войти",
       "error": "Неверный email или пароль"
     },
     "dashboard": {
       "title": "Обзор платформы",
       "totalTenants": "Всего клиентов",
       "active": "Активных",
       "trial": "На триале",
       "mrr": "MRR",
       "visits30d": "Визитов (30 дней)",
       "recentTenants": "Последние клиенты",
       "topActivity": "Топ по активности"
     },
     "tenants": {
       "title": "Клиенты",
       "search": "Поиск по названию или slug...",
       "addTenant": "Добавить клиента",
       "all": "Все",
       "trial": "Триал",
       "active": "Активные",
       "pastDue": "Просрочены",
       "cancelled": "Отменены",
       "cols": {
         "name": "Название",
         "slug": "Slug",
         "plan": "Тариф",
         "status": "Статус",
         "customers": "Клиентов",
         "visits30d": "Визитов 30д",
         "mrr": "MRR",
         "trialEnds": "Триал до",
         "actions": "Действия"
       },
       "actions": {
         "view": "Открыть",
         "impersonate": "Войти как клиент"
       },
       "empty": "Клиенты не найдены"
     },
     "tenantDetail": {
       "basicInfo": "Основная информация",
       "name": "Название",
       "slug": "Slug",
       "phone": "Телефон",
       "created": "Создан",
       "status": "Статус",
       "acceptingQueue": "Принимает очередь",
       "credentials360": "Данные 360dialog",
       "channelId": "ID канала",
       "apiKey": "API ключ",
       "edit360": "Изменить данные 360dialog",
       "impersonate": "Войти как клиент",
       "impersonateHint": "Открыть дашборд клиента от имени его админа",
       "subscription": "Подписка",
       "plan": "Тариф",
       "subStatus": "Статус",
       "monthlyPrice": "Цена в месяц ($)",
       "trialEnds": "Триал до",
       "notes": "Заметки",
       "saveSubscription": "Сохранить подписку",
       "extendTrial": "Продлить триал +7 дней",
       "blockedBanner": "Клиент заблокирован — просрочена оплата",
       "stats": "Статистика",
       "allTimeVisits": "Визитов всего",
       "allTimeRevenue": "Выручка всего",
       "totalCustomers": "Клиентов всего",
       "recentActivity": "Последние активности"
     },
     "addTenantModal": {
       "title": "Добавить клиента",
       "businessName": "Название бизнеса",
       "slug": "Slug",
       "slugHint": "Только строчные буквы, цифры и дефисы",
       "phone": "Телефон",
       "adminEmail": "Email администратора",
       "adminPassword": "Пароль администратора",
       "plan": "Тариф",
       "cancel": "Отмена",
       "create": "Создать",
       "webhookInstructions": "Укажи в 360dialog Hub webhook URL:",
       "webhookNext": "Затем добавь d360_api_key и d360_channel_id в карточке клиента."
     },
     "analytics": {
       "title": "Аналитика платформы",
       "mrrHistory": "История MRR",
       "topTenants": "Топ клиентов по выручке",
       "planDistribution": "Распределение по тарифам",
       "months": "мес."
     },
     "plans": {
       "starter": "Стартер",
       "pro": "Про",
       "business": "Бизнес",
       "enterprise": "Энтерпрайз"
     },
     "statuses": {
       "trial": "Триал",
       "active": "Активен",
       "past_due": "Просрочен",
       "cancelled": "Отменён"
     },
     "common": {
       "save": "Сохранить",
       "cancel": "Отмена",
       "loading": "Загрузка...",
       "error": "Что-то пошло не так",
       "yes": "Да",
       "no": "Нет",
       "copy": "Копировать",
       "copied": "Скопировано!",
       "reveal": "Показать",
       "hide": "Скрыть",
       "noData": "Нет данных"
     },
     "impersonation": {
       "banner": "Режим просмотра — Клиент: {name}",
       "exit": "Выйти"
     }
   }

═══════════════════════════════════════
ЧАСТЬ B — Переключатель языка
═══════════════════════════════════════

6. admin-frontend/src/components/LocaleSwitcher.vue:

   <script setup lang="ts">
   import { useI18n } from 'vue-i18n'
   const { locale } = useI18n()

   function setLocale(lang: string) {
     locale.value = lang
     localStorage.setItem('sa_locale', lang)
   }
   </script>

   <template>
     <div style="display:flex;gap:4px">
       <button
         v-for="lang in ['en', 'ru']"
         :key="lang"
         @click="setLocale(lang)"
         :style="{
           padding: '4px 10px',
           fontSize: '12px',
           fontWeight: locale === lang ? '500' : '400',
           opacity: locale === lang ? 1 : 0.5,
           border: '0.5px solid currentColor',
           borderRadius: '4px',
           background: 'transparent',
           cursor: 'pointer',
           textTransform: 'uppercase'
         }"
       >{{ lang }}</button>
     </div>
   </template>

   Добавь <LocaleSwitcher /> в правый верхний угол навбара (рядом с кнопкой Logout).
   Выбранный язык сохраняется в localStorage как 'sa_locale' и восстанавливается при перезагрузке.

═══════════════════════════════════════
ЧАСТЬ C — Применяй переводы во всех компонентах
═══════════════════════════════════════

7. Во всех .vue файлах /admin-frontend/ замени хардкоженные строки на $t():

   Правило: никаких строк напрямую в шаблонах.
   ДО:   <h1>Dashboard</h1>
   ПОСЛЕ: <h1>{{ $t('dashboard.title') }}</h1>

   ДО:   <button>Save Subscription</button>
   ПОСЛЕ: <button>{{ $t('tenantDetail.saveSubscription') }}</button>

   ДО:   placeholder="Search by name..."
   ПОСЛЕ: :placeholder="$t('tenants.search')"

   Для строк с параметрами (impersonation banner):
   {{ $t('impersonation.banner', { name: tenantName }) }}

   Обработай все файлы:
   - views/LoginView.vue
   - views/DashboardView.vue
   - views/TenantsView.vue
   - views/TenantDetailView.vue
   - views/AnalyticsView.vue
   - components/AddTenantModal.vue
   - components/NavBar.vue (или как называется навигация)
   - App.vue (impersonation banner)

8. Проверь что НЕ нужно переводить:
   - Значения из API (имена тенантов, slug, email — это данные, не UI)
   - Числа и даты (форматируй через Intl.NumberFormat / Intl.DateTimeFormat)
   - Технические строки (названия планов в select передавай через $t('plans.starter') и т.д.)

9. Форматирование дат с учётом локали:
   Создай admin-frontend/src/composables/useFormatters.ts:

   import { useI18n } from 'vue-i18n'

   export function useFormatters() {
     const { locale } = useI18n()

     function formatDate(date: string | Date): string {
       return new Intl.DateTimeFormat(locale.value === 'ru' ? 'ru-RU' : 'en-US', {
         day: '2-digit', month: 'short', year: 'numeric'
       }).format(new Date(date))
     }

     function formatMoney(amount: number): string {
       return new Intl.NumberFormat(locale.value === 'ru' ? 'ru-RU' : 'en-US', {
         style: 'currency', currency: 'USD', maximumFractionDigits: 0
       }).format(amount)
     }

     return { formatDate, formatMoney }
   }

   Используй во всех местах где показываются даты и деньги.

Чего НЕ делать:
- Не трогай /frontend/ и /backend/ — только /admin-frontend/
- Не добавляй арабский (AR) в admin panel — она только для тебя
- Не используй сторонние библиотеки переводов (только vue-i18n)
- Не переводи данные из API — только строки интерфейса
- Не создавай отдельные страницы для каждого языка — один компонент, два перевода
```

---

## СЕССИЯ 11 — Маркетинговый сайт (Astro + AR/EN/RU)

```
Создай маркетинговый сайт для QueueCRM. Это отдельный проект — не часть /frontend/ или /admin-frontend/.

Контекст: продукт готов, нужна точка входа для потенциальных клиентов.
Целевая аудитория: владельцы моек, СТО, барбершопов, салонов в Саудовской Аравии.

ВАЖНО:
- Три языка: AR (по умолчанию), EN, RU
- AR — RTL направление текста (dir="rtl")
- Сайт статический — никакого бэкенда, никакой БД
- Деплой на Vercel отдельно от продукта

═══════════════════════════════════════
ЧАСТЬ A — Настройка проекта
═══════════════════════════════════════

1. Создай /marketing/ — отдельная папка в корне репозитория:
   npm create astro@latest marketing -- --template minimal --typescript strict --no-git

2. Установи зависимости:
   npx astro add tailwind
   npx astro add @astrojs/sitemap

3. Структура /marketing/src/:
   /i18n
     ar.ts    — арабские тексты
     en.ts    — английские тексты
     ru.ts    — русские тексты
     index.ts — хелпер getLang() и useTranslations()
   /layouts
     Layout.astro   — базовый layout с head, fonts, meta
   /pages
     /ar/           — арабские страницы
       index.astro
       pricing.astro
     /en/
       index.astro
       pricing.astro
     /ru/
       index.astro
       pricing.astro
     index.astro    — редирект на /ar/ (основная аудитория KSA)
   /components
     Hero.astro
     HowItWorks.astro
     ForWhom.astro
     Pricing.astro
     FAQ.astro
     Footer.astro
     NavBar.astro
     WhatsAppButton.astro   — плавающая кнопка WhatsApp

4. /marketing/src/i18n/index.ts — хелпер локализации:

   export type Lang = 'ar' | 'en' | 'ru'
   export const defaultLang: Lang = 'ar'
   export const rtlLangs: Lang[] = ['ar']

   export function getLang(url: URL): Lang {
     const [, lang] = url.pathname.split('/')
     if (lang === 'ar' || lang === 'en' || lang === 'ru') return lang
     return defaultLang
   }

   export function useTranslations(lang: Lang) {
     return function t(key: string): string {
       const translations = { ar, en, ru }
       return key.split('.').reduce((obj: any, k) => obj?.[k], translations[lang]) ?? key
     }
   }

═══════════════════════════════════════
ЧАСТЬ B — Контент (все три языка)
═══════════════════════════════════════

5. /marketing/src/i18n/ar.ts — арабский (основной):

   export const ar = {
     meta: {
       title: "QueueCRM — نظام إدارة الطوابير عبر واتساب",
       description: "إدارة الطوابير وبيانات العملاء عبر واتساب. بدون تطبيق. للمراكز والصالونات وغسيل السيارات."
     },
     nav: {
       howItWorks: "كيف يعمل",
       forWhom: "لمن",
       pricing: "الأسعار",
       startTrial: "ابدأ مجاناً"
     },
     hero: {
       badge: "للسوق السعودي",
       headline: "العملاء لا ينتظرون — يأتون في الوقت المناسب",
       subheadline: "نظام إدارة الطوابير عبر واتساب. بدون تطبيق. يعمل مع كل هاتف.",
       cta: "جرب مجاناً 30 يوماً",
       ctaSecondary: "شاهد كيف يعمل",
       stat1: "97%",
       stat1label: "نسبة استخدام واتساب في السعودية",
       stat2: "−40%",
       stat2label: "تراجع في فقدان العملاء",
       stat3: "30 دقيقة",
       stat3label: "وقت الإعداد"
     },
     problem: {
       title: "هل تعاني من هذا؟",
       item1: "العملاء يأتون، ينتظرون، ويغادرون",
       item2: "لا توجد شفافية في وقت الانتظار",
       item3: "لا يوجد سجل للعملاء أو تاريخ للزيارات",
       item4: "التواصل يدوي وغير منظم"
     },
     howItWorks: {
       title: "كيف يعمل",
       step1title: "العميل يرسل رسالة",
       step1desc: "يكتب في واتساب أو يمسح رمز QR عند المدخل",
       step2title: "البوت يرد فوراً",
       step2desc: "يختار الخدمة، يرى موقعه في الطابور والوقت المتوقع",
       step3title: "إشعار تلقائي",
       step3desc: "\"دورك بعد 20 دقيقة\" — العميل يأتي في الوقت المناسب"
     },
     forWhom: {
       title: "مناسب لـ",
       item1: "غسيل السيارات",
       item2: "مراكز الصيانة",
       item3: "تغيير الإطارات",
       item4: "الصالونات",
       item5: "الحلاقين",
       item6: "الوكالات"
     },
     pricing: {
       title: "الأسعار",
       subtitle: "تجربة مجانية 30 يوماً — بدون بطاقة ائتمان",
       perMonth: "/ شهر",
       popular: "الأكثر طلباً",
       plans: {
         starter: {
           name: "ستارتر",
           price: "187",
           priceSAR: "700",
           desc: "للمشاريع الصغيرة",
           features: ["طابور واحد", "إشعارات واتساب", "لوحة تحكم بسيطة", "دعم فني"]
         },
         pro: {
           name: "برو",
           price: "562",
           priceSAR: "2100",
           desc: "للمشاريع النشطة",
           features: ["طوابير غير محدودة", "CRM كامل", "أولوية VIP", "تحليلات متقدمة", "دعم أولوية"]
         },
         business: {
           name: "بيزنس",
           price: "1125",
           priceSAR: "4200",
           desc: "للشبكات والفروع",
           features: ["فروع متعددة", "تقارير متقدمة", "تكامل مخصص", "مدير حساب", "SLA مضمون"]
         }
       }
     },
     faq: {
       title: "الأسئلة الشائعة",
       items: [
         {
           q: "هل يحتاج العميل لتثبيت تطبيق؟",
           a: "لا. كل شيء يعمل عبر واتساب الذي لديهم بالفعل."
         },
         {
           q: "كيف يدخل العميل للطابور؟",
           a: "يمسح رمز QR عند المدخل أو يرسل رسالة مباشرة لرقم الواتساب."
         },
         {
           q: "هل يعمل باللغة العربية؟",
           a: "نعم، النظام يدعم العربية والإنجليزية تلقائياً حسب لغة رسالة العميل."
         },
         {
           q: "ماذا لو لم يكن لدي خبرة تقنية؟",
           a: "الإعداد يستغرق 30 دقيقة. فريقنا يساعدك في كل خطوة."
         }
       ]
     },
     footer: {
       tagline: "إدارة الطوابير عبر واتساب",
       contact: "تواصل معنا",
       whatsapp: "واتساب",
       rights: "جميع الحقوق محفوظة"
     },
     whatsappButton: "تحدث معنا"
   }

6. /marketing/src/i18n/en.ts — английский:

   export const en = {
     meta: {
       title: "QueueCRM — WhatsApp Queue Management for Auto Business",
       description: "Manage queues and customers via WhatsApp. No app needed. For car washes, service centers, salons."
     },
     nav: {
       howItWorks: "How it works",
       forWhom: "For whom",
       pricing: "Pricing",
       startTrial: "Start free trial"
     },
     hero: {
       badge: "Built for Saudi Arabia",
       headline: "Customers don't wait — they arrive on time",
       subheadline: "WhatsApp queue management. No app. Works on any phone.",
       cta: "Start 30-day free trial",
       ctaSecondary: "See how it works",
       stat1: "97%",
       stat1label: "WhatsApp penetration in KSA",
       stat2: "−40%",
       stat2label: "Reduction in lost customers",
       stat3: "30 min",
       stat3label: "Setup time"
     },
     problem: {
       title: "Sound familiar?",
       item1: "Customers arrive, wait, and leave",
       item2: "No transparency on wait time",
       item3: "No customer records or visit history",
       item4: "Manual, unorganized communication"
     },
     howItWorks: {
       title: "How it works",
       step1title: "Customer sends a message",
       step1desc: "Texts on WhatsApp or scans QR code at the entrance",
       step2title: "Bot replies instantly",
       step2desc: "Picks service, sees position in queue and estimated wait",
       step3title: "Automatic notification",
       step3desc: "\"Your turn in 20 minutes\" — customer arrives right on time"
     },
     forWhom: {
       title: "Perfect for",
       item1: "Car washes",
       item2: "Service centers",
       item3: "Tire shops",
       item4: "Beauty salons",
       item5: "Barbershops",
       item6: "Dealerships"
     },
     pricing: {
       title: "Pricing",
       subtitle: "30-day free trial — no credit card required",
       perMonth: "/ month",
       popular: "Most popular",
       plans: {
         starter: {
           name: "Starter",
           price: "50",
           priceSAR: "188",
           desc: "For small businesses",
           features: ["Single queue", "WhatsApp notifications", "Basic dashboard", "Support"]
         },
         pro: {
           name: "Pro",
           price: "150",
           priceSAR: "563",
           desc: "For busy businesses",
           features: ["Unlimited queues", "Full CRM", "VIP priority", "Advanced analytics", "Priority support"]
         },
         business: {
           name: "Business",
           price: "300",
           priceSAR: "1125",
           desc: "For chains and networks",
           features: ["Multiple branches", "Advanced reports", "Custom integration", "Account manager", "SLA guarantee"]
         }
       }
     },
     faq: {
       title: "FAQ",
       items: [
         {
           q: "Does the customer need to install an app?",
           a: "No. Everything works through WhatsApp they already have."
         },
         {
           q: "How does a customer join the queue?",
           a: "They scan a QR code at the entrance or message the WhatsApp number directly."
         },
         {
           q: "Does it support Arabic?",
           a: "Yes, the system auto-detects the language from the customer's message."
         },
         {
           q: "What if I'm not tech-savvy?",
           a: "Setup takes 30 minutes. Our team guides you through every step."
         }
       ]
     },
     footer: {
       tagline: "WhatsApp queue management",
       contact: "Contact us",
       whatsapp: "WhatsApp",
       rights: "All rights reserved"
     },
     whatsappButton: "Chat with us"
   }

7. /marketing/src/i18n/ru.ts — русский:

   export const ru = {
     meta: {
       title: "QueueCRM — управление очередями через WhatsApp",
       description: "Управляй очередями и клиентами через WhatsApp. Без приложения. Для моек, СТО, салонов."
     },
     nav: {
       howItWorks: "Как работает",
       forWhom: "Для кого",
       pricing: "Тарифы",
       startTrial: "Начать бесплатно"
     },
     hero: {
       badge: "Создано для рынка KSA",
       headline: "Клиенты не ждут — приезжают вовремя",
       subheadline: "Управление очередями через WhatsApp. Без приложения. Работает на любом телефоне.",
       cta: "Начать бесплатно на 30 дней",
       ctaSecondary: "Посмотреть демо",
       stat1: "97%",
       stat1label: "Покрытие WhatsApp в Саудовской Аравии",
       stat2: "−40%",
       stat2label: "Снижение потери клиентов",
       stat3: "30 мин",
       stat3label: "Время настройки"
     },
     problem: {
       title: "Узнаёшь?",
       item1: "Клиенты приезжают, ждут и уезжают",
       item2: "Нет прозрачности по времени ожидания",
       item3: "Нет базы клиентов и истории визитов",
       item4: "Коммуникация ручная и неструктурированная"
     },
     howItWorks: {
       title: "Как это работает",
       step1title: "Клиент пишет сообщение",
       step1desc: "Пишет в WhatsApp или сканирует QR-код на входе",
       step2title: "Бот отвечает мгновенно",
       step2desc: "Выбирает услугу, видит позицию в очереди и ETA",
       step3title: "Автоматическое уведомление",
       step3desc: "\"Через 20 минут ваша очередь\" — клиент приезжает вовремя"
     },
     forWhom: {
       title: "Подходит для",
       item1: "Автомоек",
       item2: "СТО",
       item3: "Шиномонтажей",
       item4: "Салонов красоты",
       item5: "Барбершопов",
       item6: "Дилеров"
     },
     pricing: {
       title: "Тарифы",
       subtitle: "30 дней бесплатно — без привязки карты",
       perMonth: "/ мес",
       popular: "Популярный",
       plans: {
         starter: {
           name: "Стартер",
           price: "50",
           priceSAR: "188",
           desc: "Для малого бизнеса",
           features: ["Одна очередь", "WhatsApp уведомления", "Базовый дашборд", "Поддержка"]
         },
         pro: {
           name: "Про",
           price: "150",
           priceSAR: "563",
           desc: "Для активного бизнеса",
           features: ["Неограниченные очереди", "Полный CRM", "VIP приоритет", "Аналитика", "Приоритетная поддержка"]
         },
         business: {
           name: "Бизнес",
           price: "300",
           priceSAR: "1125",
           desc: "Для сетей и франшиз",
           features: ["Несколько точек", "Расширенные отчёты", "Кастомная интеграция", "Менеджер аккаунта", "Гарантия SLA"]
         }
       }
     },
     faq: {
       title: "Частые вопросы",
       items: [
         {
           q: "Нужно ли клиенту устанавливать приложение?",
           a: "Нет. Всё работает через WhatsApp, который уже установлен."
         },
         {
           q: "Как клиент встаёт в очередь?",
           a: "Сканирует QR-код на входе или пишет напрямую в WhatsApp."
         },
         {
           q: "Поддерживается ли арабский язык?",
           a: "Да, система автоматически определяет язык по сообщению клиента."
         },
         {
           q: "Нужны ли технические знания?",
           a: "Настройка занимает 30 минут. Наша команда помогает на каждом шаге."
         }
       ]
     },
     footer: {
       tagline: "Управление очередями через WhatsApp",
       contact: "Связаться",
       whatsapp: "WhatsApp",
       rights: "Все права защищены"
     },
     whatsappButton: "Написать нам"
   }

═══════════════════════════════════════
ЧАСТЬ C — Компоненты и страницы
═══════════════════════════════════════

8. /marketing/src/layouts/Layout.astro:
   - Принимает props: lang, title, description
   - Устанавливает <html lang={lang} dir={isRTL ? 'rtl' : 'ltr'}>
   - Google Fonts: для AR — Noto Kufi Arabic, для EN/RU — Inter
   - Meta tags: og:title, og:description, og:type, canonical URL
   - Подключает NavBar и WhatsAppButton

9. /marketing/src/pages/index.astro — редирект:
   ---
   return Astro.redirect('/ar/')
   ---

10. /marketing/src/pages/ar/index.astro — арабская главная:
    ---
    import Layout from '../../layouts/Layout.astro'
    import { ar } from '../../i18n/ar'
    import Hero from '../../components/Hero.astro'
    ... все компоненты
    const t = ar
    ---
    <Layout lang="ar" title={t.meta.title} description={t.meta.description}>
      <Hero {t} />
      <HowItWorks {t} />
      <ForWhom {t} />
      <Pricing {t} />
      <FAQ {t} />
    </Layout>

    Аналогично /en/index.astro и /ru/index.astro с соответствующими переводами.

11. /marketing/src/components/NavBar.astro:
    - Принимает lang и t (переводы)
    - Логотип: "QueueCRM" слева (или справа для AR)
    - Ссылки: How it works / Pricing
    - Кнопка "Start free trial" — ссылка на {DASHBOARD_URL}/login
    - Переключатель языков: AR | EN | RU
      Клик переключает: /ar/ → /en/ → /ru/ (замена первого сегмента URL)
    - RTL: для lang=ar весь nav зеркалится (flexDirection: row-reverse)

12. /marketing/src/components/Hero.astro:
    - Бейдж (badge) с текстом
    - H1 — главный заголовок (крупно, жирно)
    - Подзаголовок
    - Две кнопки: основная CTA + вторичная
    - Три stat карточки в ряд (stat1, stat2, stat3)
    - Дизайн: чистый, светлый фон, без градиентов

13. /marketing/src/components/WhatsAppButton.astro:
    - Фиксированная круглая кнопка в правом нижнем углу (левом для AR)
    - Зелёный цвет (#25D366)
    - Ссылка: https://wa.me/НОМЕР?text=Хочу+узнать+о+QueueCRM
      Номер берётся из env PUBLIC_WHATSAPP_NUMBER
    - Tooltip с текстом t.whatsappButton при hover

14. /marketing/src/components/Pricing.astro:
    - Три карточки: Starter, Pro, Business
    - Pro — выделена (border accent, бейдж "Popular")
    - Цена показывается в USD + в SAR (1 USD = 3.75 SAR)
    - Список features с галочками
    - Кнопка "Start free trial" на каждой карточке

15. /marketing/.env.example:
    PUBLIC_WHATSAPP_NUMBER=966501234567
    PUBLIC_DASHBOARD_URL=https://app.qcrm.sa
    PUBLIC_SITE_URL=https://qcrm.sa

16. /marketing/astro.config.mjs:
    import { defineConfig } from 'astro/config'
    import tailwind from '@astrojs/tailwind'
    import sitemap from '@astrojs/sitemap'

    export default defineConfig({
      site: 'https://qcrm.sa',
      integrations: [tailwind(), sitemap()],
      i18n: {
        defaultLocale: 'ar',
        locales: ['ar', 'en', 'ru'],
        routing: { prefixDefaultLocale: true }
      }
    })

17. /marketing/vercel.json:
    {
      "redirects": [
        { "source": "/", "destination": "/ar/", "permanent": false }
      ]
    }

Чего НЕ делать:
- Не подключай к backend (статический сайт, никаких API вызовов)
- Не добавляй форму регистрации — только кнопка Start Trial (ссылка на /login)
- Не добавляй блог, кейсы, команду (это v2)
- Не используй UI-фреймворки (shadcn и т.д.) — только Astro + Tailwind
- Не добавляй анимации и сложные эффекты — чистый, быстрый, читаемый
- Не хардкоди номер WhatsApp — только из env
```

---

## БОНУС — Промпт для исправления ошибок

Когда Claude Code что-то сломал или сделал не так:

```
В файле [путь к файлу] есть проблема:

[опиши проблему точно — что происходит vs что должно происходить]

Контекст из CLAUDE.md: [вставь релевантный раздел]

Требования к исправлению:
1. Исправь только [конкретная функция/класс/логика]
2. Не меняй [что не трогать]
3. После исправления напиши тест который воспроизводит баг и проверяет фикс

Не переписывай весь файл — только исправь проблемный участок.
```

---

## СЕССИЯ 12 — Деплой на Render + Upstash (бесплатно)

```
Read CLAUDE.md. All code is ready. Now prepare everything for free deployment.

Platform: Render.com (backend + static sites) + Upstash.com (Redis).
Goal: create all config files so I can deploy by clicking "Connect repo" in Render.

Do NOT run any deploy commands — only create files and print instructions.
Do NOT install any CLI tools.

═══════════════════════════════════════
ЧАСТЬ A — Конфиг файлы
═══════════════════════════════════════

1. Create render.yaml in project root:

   Copy this exactly — spacing matters for YAML:

   services:
     - type: web
       name: qcrm-backend
       runtime: python
       rootDir: backend
       buildCommand: pip install -r requirements.txt
       startCommand: alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
       plan: free
       healthCheckPath: /health
       envVars:
         - key: DATABASE_URL
           fromDatabase:
             name: qcrm-db
             property: connectionString
         - key: REDIS_URL
           sync: false
         - key: JWT_SECRET_KEY
           generateValue: true
         - key: WEBHOOK_SECRET_PATH
           generateValue: true
         - key: PUBLIC_APP_URL
           value: https://qcrm-site.onrender.com
         - key: ALLOWED_ORIGINS
           value: https://qcrm-dashboard.onrender.com,https://qcrm-admin.onrender.com,https://qcrm-site.onrender.com
         - key: D360_API_URL
           value: https://waba.360dialog.io/v1
         - key: D360_PARTNER_TOKEN
           sync: false
         - key: SEED_ADMIN_EMAIL
           value: admin@qcrm-demo.sa
         - key: SEED_ADMIN_PASSWORD
           sync: false

     - type: web
       name: qcrm-dashboard
       runtime: static
       rootDir: frontend
       buildCommand: npm install && npm run build
       staticPublishPath: dist
       plan: free
       envVars:
         - key: VITE_API_URL
           value: https://qcrm-backend.onrender.com
         - key: VITE_WS_URL
           value: wss://qcrm-backend.onrender.com

     - type: web
       name: qcrm-admin
       runtime: static
       rootDir: admin-frontend
       buildCommand: npm install && npm run build
       staticPublishPath: dist
       plan: free
       envVars:
         - key: VITE_API_URL
           value: https://qcrm-backend.onrender.com
         - key: VITE_TENANT_DASHBOARD_URL
           value: https://qcrm-dashboard.onrender.com

     - type: web
       name: qcrm-site
       runtime: static
       rootDir: marketing
       buildCommand: npm install && npm run build
       staticPublishPath: dist
       plan: free
       envVars:
         - key: PUBLIC_WHATSAPP_NUMBER
           sync: false
         - key: PUBLIC_DASHBOARD_URL
           value: https://qcrm-dashboard.onrender.com
         - key: PUBLIC_SITE_URL
           value: https://qcrm-site.onrender.com

   databases:
     - name: qcrm-db
       plan: free
       databaseName: qcrm
       user: qcrm

2. Create .env.render-checklist in project root:

   # ═══════════════════════════════════════════════════
   # RENDER — ЧТО ЗАПОЛНЯТЬ ВРУЧНУЮ В DASHBOARD
   # ═══════════════════════════════════════════════════
   #
   # 1. REDIS_URL (сервис qcrm-backend)
   #    Получи: upstash.com → Create Database → Redis → Free
   #    Скопируй "UPSTASH_REDIS_URL" (rediss://...)
   #
   # 2. D360_PARTNER_TOKEN (сервис qcrm-backend)
   #    Получи: 360dialog Partner Hub → API Credentials
   #
   # 3. SEED_ADMIN_PASSWORD (сервис qcrm-backend)
   #    Придумай сильный пароль (мин. 12 символов)
   #
   # 4. PUBLIC_WHATSAPP_NUMBER (сервис qcrm-site)
   #    Номер WhatsApp без + (например: 966501234567)
   #
   # ═══════════════════════════════════════════════════
   # ПОСЛЕ ДЕПЛОЯ — выполни в Render Shell
   # ═══════════════════════════════════════════════════
   # Render → qcrm-backend → Shell:
   #
   #   python scripts/seed.py
   #
   #   python scripts/create_super_admin.py \
   #     --email твой@email.com \
   #     --password ТвойПароль123
   # ═══════════════════════════════════════════════════

3. Create cron-job-keep-alive.md:

   # Чтобы бэкенд не засыпал на бесплатном плане Render
   #
   # 1. Зайди на cron-job.org (бесплатно, без карты)
   # 2. Sign up → Create cronjob
   # 3. URL: https://qcrm-backend.onrender.com/health
   # 4. Schedule: Every 10 minutes
   # 5. Save
   #
   # Без этого первый запрос после 15 мин простоя займёт 30 сек.
   # С этим — бэкенд всегда онлайн во время демо.

4. Add .renderignore in project root:
   node_modules/
   __pycache__/
   *.pyc
   .env
   .env.local
   slide-*.jpg
   *.pdf
   build_pptx.js
   QueueCRM_Presentation.pptx

═══════════════════════════════════════
ЧАСТЬ B — Проверка перед деплоем
═══════════════════════════════════════

5. Check and fix if needed:

   backend/app/core/config.py — убедись что ALLOWED_ORIGINS парсится из строки:

   allowed_origins: list[str] = ["http://localhost:5173"]

   @validator("allowed_origins", pre=True)
   def parse_origins(cls, v):
       if isinstance(v, str):
           return [o.strip() for o in v.split(",")]
       return v

   backend/app/main.py — убедись что CORS использует список:
   allow_origins=settings.allowed_origins

   marketing/astro.config.mjs — добавь output: 'static' если нет:
   export default defineConfig({
     output: 'static',
     ...
   })

   frontend/vite.config.ts и admin-frontend/vite.config.ts:
   Убедись что build.outDir = 'dist' (это дефолт, но проверь)

6. Check all these files exist:
   - render.yaml (только что создан)
   - backend/requirements.txt
   - backend/alembic.ini
   - backend/alembic/env.py
   - frontend/package.json
   - admin-frontend/package.json
   - marketing/package.json

   Если какого-то файла нет — сообщи мне, не создавай его сам.

7. Git commit:
   git add render.yaml .renderignore .env.render-checklist cron-job-keep-alive.md
   git add -u
   git commit -m "chore: add Render.com deployment config"
   git push

═══════════════════════════════════════
ЧАСТЬ C — Напечатай инструкцию
═══════════════════════════════════════

8. After completing all steps, print this exactly:

   ════════════════════════════════════════════
   ДЕПЛОЙ ГОТОВ — ЧТО ДЕЛАТЬ ДАЛЬШЕ
   ════════════════════════════════════════════

   ШАГ 1 — Upstash Redis (2 мин, бесплатно)
   Открой: upstash.com
   → Sign up → Create Database → Redis → Free
   → Скопируй UPSTASH_REDIS_URL (rediss://...)

   ШАГ 2 — Render (5 мин, бесплатно)
   Открой: render.com
   → Sign up через GitHub
   → New → Blueprint → Connect repo
   → Render найдёт render.yaml → создаст всё автоматически
   → Подождёт 5-10 минут пока задеплоится

   ШАГ 3 — Заполни env переменные
   Render → qcrm-backend → Environment → Add:
     REDIS_URL         = [из Upstash]
     D360_PARTNER_TOKEN = [из 360dialog]
     SEED_ADMIN_PASSWORD = [твой пароль]
   Render → qcrm-site → Environment → Add:
     PUBLIC_WHATSAPP_NUMBER = [номер без +]
   Нажми "Save Changes" → сервисы перезапустятся

   ШАГ 4 — Seed данные
   Render → qcrm-backend → Shell → введи:
     python scripts/seed.py
     python scripts/create_super_admin.py --email ты@email.com --password Пароль

   ШАГ 5 — Keep-alive (не даёт засыпать)
   Открой: cron-job.org → Create cronjob
   URL: https://qcrm-backend.onrender.com/health
   Schedule: Every 10 minutes → Save

   ════════════════════════════════════════════
   ГОТОВЫЕ ССЫЛКИ (появятся после деплоя):
   ════════════════════════════════════════════
   Сайт:     https://qcrm-site.onrender.com
   Дашборд:  https://qcrm-dashboard.onrender.com
   Админка:  https://qcrm-admin.onrender.com
   API docs: https://qcrm-backend.onrender.com/docs
   ════════════════════════════════════════════
   Смотри .env.render-checklist для деталей
   ════════════════════════════════════════════

Чего НЕ делать:
- Не запускай render deploy — всё деплоится автоматически через GitHub push
- Не коммить реальные пароли в git — только через Render Dashboard
- Не меняй имена сервисов (qcrm-backend, qcrm-dashboard...) —
  они вписаны в ALLOWED_ORIGINS и VITE_API_URL
- Не используй этот деплой для продакшена —
  PostgreSQL на Render бесплатен только 90 дней
```

---

## ВАЖНЫЕ ПРАВИЛА для всех сессий

**Всегда добавляй в начало промпта:**
- "Читай CLAUDE.md перед началом"
- "Не создавай ничего кроме того что описано"

**Никогда не проси Claude Code:**
- Написать всё сразу в одном промпте
- "Сделай как лучше" — всегда конкретизируй
- Добавить "улучшения по своему усмотрению"

**Если сессия стала длинной (> 20 сообщений):**
- Начни новую сессию
- В начале новой сессии скажи: "Мы продолжаем проект QueueCRM. Прочитай CLAUDE.md. Предыдущая задача [X] завершена."
