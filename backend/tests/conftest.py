"""Shared pytest fixtures."""
import asyncio
import os
import uuid
import datetime
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text

from dotenv import load_dotenv
load_dotenv(".env.test", override=True)

from app.core.config import settings
from app.core.database import Base
from app.core.deps import get_db, get_redis, set_redis_pool
from app.core.security import hash_password
from app.main import app as fastapi_app
from app.models.staff_user import StaffUser, StaffRole
from app.models.super_admin import SuperAdmin
from app.models.tenant import Tenant, BusinessType
from app.models.tenant_subscription import TenantSubscription, SubscriptionStatus

# Import all models so metadata is complete
import app.models  # noqa: F401

# ---------------------------------------------------------------------------
# Test DB engine
# ---------------------------------------------------------------------------

# .env.test already points to queuecrm_test
test_engine = create_async_engine(settings.DATABASE_URL, echo=False)
TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

TABLES_TO_TRUNCATE = [
    "queue_entries",
    "whatsapp_sessions",
    "staff_users",
    "super_admins",
    "tenant_subscriptions",
    "customers",
    "services",
    "tenants",
]


@pytest.fixture(scope="session")
def event_loop():
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_tables():
    """Create all tables once per session."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def clean_tables(setup_tables):
    """Truncate all tables before each test."""
    async with test_engine.begin() as conn:
        tables = ", ".join(TABLES_TO_TRUNCATE)
        await conn.execute(
            text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE")
        )


# ---------------------------------------------------------------------------
# Per-test DB session
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db_session(clean_tables) -> AsyncGenerator[AsyncSession, None]:
    async with TestSession() as session:
        yield session


# ---------------------------------------------------------------------------
# Redis
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def redis() -> AsyncGenerator[Redis, None]:
    r = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    await r.flushdb()
    set_redis_pool(r)
    yield r
    await r.flushdb()
    await r.aclose()


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client(db_session: AsyncSession, redis: Redis) -> AsyncGenerator[AsyncClient, None]:
    async def override_db():
        yield db_session

    async def override_redis():
        return redis

    fastapi_app.dependency_overrides[get_db] = override_db
    fastapi_app.dependency_overrides[get_redis] = override_redis

    async with AsyncClient(
        transport=ASGITransport(app=fastapi_app), base_url="http://test"
    ) as ac:
        yield ac

    fastapi_app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def sample_tenant(db_session: AsyncSession) -> Tenant:
    tenant = Tenant(
        id=uuid.uuid4(),
        name="Test Garage",
        slug=f"test-garage-{uuid.uuid4().hex[:6]}",
        business_type=BusinessType.auto_service,
        phone="+966500000001",
    )
    db_session.add(tenant)

    trial_end = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)
    sub = TenantSubscription(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        status=SubscriptionStatus.trial,
        trial_ends_at=trial_end,
    )
    db_session.add(sub)
    await db_session.commit()
    return tenant


@pytest_asyncio.fixture
async def sample_admin(db_session: AsyncSession, sample_tenant: Tenant) -> StaffUser:
    user = StaffUser(
        id=uuid.uuid4(),
        tenant_id=sample_tenant.id,
        email=f"admin-{uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("password123"),
        full_name="Test Admin",
        role=StaffRole.admin,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def sample_operator(db_session: AsyncSession, sample_tenant: Tenant) -> StaffUser:
    user = StaffUser(
        id=uuid.uuid4(),
        tenant_id=sample_tenant.id,
        email=f"operator-{uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("password123"),
        full_name="Test Operator",
        role=StaffRole.operator,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def sample_super_admin(db_session: AsyncSession) -> SuperAdmin:
    admin = SuperAdmin(
        id=uuid.uuid4(),
        email=f"superadmin-{uuid.uuid4().hex[:6]}@test.com",
        hashed_password=hash_password("supersecret"),
        full_name="Super Admin",
    )
    db_session.add(admin)
    await db_session.commit()
    return admin


# ---------------------------------------------------------------------------
# Auth headers
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def admin_headers(client: AsyncClient, sample_admin: StaffUser) -> dict:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": sample_admin.email, "password": "password123"},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest_asyncio.fixture
async def operator_headers(client: AsyncClient, sample_operator: StaffUser) -> dict:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": sample_operator.email, "password": "password123"},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest_asyncio.fixture
async def super_admin_headers(client: AsyncClient, sample_super_admin: SuperAdmin) -> dict:
    resp = await client.post(
        "/api/v1/auth/super-admin/login",
        json={"email": sample_super_admin.email, "password": "supersecret"},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}
