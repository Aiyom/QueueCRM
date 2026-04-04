"""Tests for queue endpoints."""
import uuid
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def sample_service(db_session, sample_tenant):
    from app.models.service import Service
    svc = Service(
        id=uuid.uuid4(),
        tenant_id=sample_tenant.id,
        name_ar="غسيل سيارة",
        name_en="Car Wash",
        avg_duration_minutes=20,
    )
    db_session.add(svc)
    await db_session.commit()
    return svc


@pytest.fixture
async def sample_customer(db_session, sample_tenant):
    from app.models.customer import Customer
    c = Customer(
        id=uuid.uuid4(),
        tenant_id=sample_tenant.id,
        phone="+966501234567",
        name="Ahmed",
    )
    db_session.add(c)
    await db_session.commit()
    return c


class TestQueueFlow:
    async def test_get_empty_queue(
        self, client: AsyncClient, admin_headers, sample_tenant
    ):
        resp = await client.get("/api/v1/queue/", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_add_to_queue(
        self, client: AsyncClient, admin_headers, sample_customer, sample_service
    ):
        resp = await client.post(
            "/api/v1/queue/add",
            headers=admin_headers,
            json={
                "customer_id": str(sample_customer.id),
                "service_id": str(sample_service.id),
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "waiting"
        assert data["customer_id"] == str(sample_customer.id)
        return data["id"]

    async def test_add_duplicate_rejected(
        self, client: AsyncClient, admin_headers, sample_customer, sample_service
    ):
        # Add once
        await client.post(
            "/api/v1/queue/add",
            headers=admin_headers,
            json={"customer_id": str(sample_customer.id), "service_id": str(sample_service.id)},
        )
        # Add again — should fail
        resp = await client.post(
            "/api/v1/queue/add",
            headers=admin_headers,
            json={"customer_id": str(sample_customer.id), "service_id": str(sample_service.id)},
        )
        assert resp.status_code == 400

    async def test_call_next(
        self, client: AsyncClient, admin_headers, sample_customer, sample_service
    ):
        # Add first
        add_resp = await client.post(
            "/api/v1/queue/add",
            headers=admin_headers,
            json={"customer_id": str(sample_customer.id), "service_id": str(sample_service.id)},
        )
        assert add_resp.status_code == 201

        # Call next
        resp = await client.post("/api/v1/queue/call-next", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "called"

    async def test_call_next_empty_queue(
        self, client: AsyncClient, admin_headers
    ):
        resp = await client.post("/api/v1/queue/call-next", headers=admin_headers)
        assert resp.status_code == 404

    async def test_full_flow(
        self, client: AsyncClient, admin_headers, sample_customer, sample_service
    ):
        """waiting → called → in_service → done"""
        # Add
        add_resp = await client.post(
            "/api/v1/queue/add",
            headers=admin_headers,
            json={"customer_id": str(sample_customer.id), "service_id": str(sample_service.id)},
        )
        entry_id = add_resp.json()["id"]

        # Call next
        await client.post("/api/v1/queue/call-next", headers=admin_headers)

        # Start service
        resp = await client.post(
            f"/api/v1/queue/{entry_id}/start", headers=admin_headers
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_service"

        # Finish
        resp = await client.post(
            f"/api/v1/queue/{entry_id}/finish",
            headers=admin_headers,
            json={"amount": 150.0, "notes": "All good"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "done"

    async def test_cancel(
        self, client: AsyncClient, admin_headers, sample_customer, sample_service
    ):
        add_resp = await client.post(
            "/api/v1/queue/add",
            headers=admin_headers,
            json={"customer_id": str(sample_customer.id), "service_id": str(sample_service.id)},
        )
        entry_id = add_resp.json()["id"]

        resp = await client.post(
            f"/api/v1/queue/{entry_id}/cancel", headers=admin_headers
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    async def test_no_show(
        self, client: AsyncClient, admin_headers, sample_customer, sample_service
    ):
        await client.post(
            "/api/v1/queue/add",
            headers=admin_headers,
            json={"customer_id": str(sample_customer.id), "service_id": str(sample_service.id)},
        )
        call_resp = await client.post("/api/v1/queue/call-next", headers=admin_headers)
        entry_id = call_resp.json()["id"]

        resp = await client.post(
            f"/api/v1/queue/{entry_id}/no-show", headers=admin_headers
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "no_show"

    async def test_queue_stats(
        self, client: AsyncClient, admin_headers
    ):
        resp = await client.get("/api/v1/queue/stats", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_waiting" in data
        assert "is_accepting_queue" in data
