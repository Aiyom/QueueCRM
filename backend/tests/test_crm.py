"""Tests for CRM endpoints (customers, services)."""
import uuid
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestServices:
    async def test_create_service(self, client: AsyncClient, admin_headers):
        resp = await client.post(
            "/api/v1/services/",
            headers=admin_headers,
            json={"name_ar": "تغيير زيت", "name_en": "Oil Change", "avg_duration_minutes": 30},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name_en"] == "Oil Change"
        assert data["is_active"] is True

    async def test_list_services(self, client: AsyncClient, admin_headers):
        await client.post(
            "/api/v1/services/",
            headers=admin_headers,
            json={"name_ar": "خدمة", "name_en": "Service A"},
        )
        resp = await client.get("/api/v1/services/", headers=admin_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_update_service(self, client: AsyncClient, admin_headers):
        create = await client.post(
            "/api/v1/services/",
            headers=admin_headers,
            json={"name_ar": "اختبار", "name_en": "Test", "avg_duration_minutes": 15},
        )
        service_id = create.json()["id"]

        resp = await client.patch(
            f"/api/v1/services/{service_id}",
            headers=admin_headers,
            json={"avg_duration_minutes": 25},
        )
        assert resp.status_code == 200
        assert resp.json()["avg_duration_minutes"] == 25

    async def test_delete_service(self, client: AsyncClient, admin_headers):
        create = await client.post(
            "/api/v1/services/",
            headers=admin_headers,
            json={"name_ar": "حذف", "name_en": "Delete Me"},
        )
        service_id = create.json()["id"]

        resp = await client.delete(
            f"/api/v1/services/{service_id}",
            headers=admin_headers,
        )
        assert resp.status_code == 204

        # Should not appear in list
        list_resp = await client.get("/api/v1/services/", headers=admin_headers)
        ids = [s["id"] for s in list_resp.json()]
        assert service_id not in ids

    async def test_operator_cannot_create_service(
        self, client: AsyncClient, operator_headers
    ):
        resp = await client.post(
            "/api/v1/services/",
            headers=operator_headers,
            json={"name_ar": "خدمة", "name_en": "Nope"},
        )
        assert resp.status_code == 403


class TestCustomers:
    async def test_create_customer(self, client: AsyncClient, admin_headers):
        resp = await client.post(
            "/api/v1/customers/",
            headers=admin_headers,
            json={"phone": "+966501111111", "name": "Ahmed"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["phone"] == "+966501111111"
        assert data["is_vip"] is False

    async def test_duplicate_phone_rejected(self, client: AsyncClient, admin_headers):
        await client.post(
            "/api/v1/customers/",
            headers=admin_headers,
            json={"phone": "+966502222222"},
        )
        resp = await client.post(
            "/api/v1/customers/",
            headers=admin_headers,
            json={"phone": "+966502222222"},
        )
        assert resp.status_code == 409

    async def test_list_customers(self, client: AsyncClient, admin_headers):
        await client.post(
            "/api/v1/customers/",
            headers=admin_headers,
            json={"phone": "+966503333333", "name": "Mohammed"},
        )
        resp = await client.get("/api/v1/customers/", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    async def test_search_customer(self, client: AsyncClient, admin_headers):
        await client.post(
            "/api/v1/customers/",
            headers=admin_headers,
            json={"phone": "+966504444444", "name": "Khalid VIP"},
        )
        resp = await client.get(
            "/api/v1/customers/?search=Khalid", headers=admin_headers
        )
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_get_customer(self, client: AsyncClient, admin_headers):
        create = await client.post(
            "/api/v1/customers/",
            headers=admin_headers,
            json={"phone": "+966505555555"},
        )
        customer_id = create.json()["id"]
        resp = await client.get(
            f"/api/v1/customers/{customer_id}", headers=admin_headers
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == customer_id

    async def test_update_customer_vip(self, client: AsyncClient, admin_headers):
        create = await client.post(
            "/api/v1/customers/",
            headers=admin_headers,
            json={"phone": "+966506666666"},
        )
        customer_id = create.json()["id"]

        resp = await client.patch(
            f"/api/v1/customers/{customer_id}",
            headers=admin_headers,
            json={"is_vip": True},
        )
        assert resp.status_code == 200
        assert resp.json()["is_vip"] is True
        assert resp.json()["vip_set_manually"] is True

    async def test_segments_stats(self, client: AsyncClient, admin_headers):
        resp = await client.get(
            "/api/v1/customers/segments/stats", headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total_customers" in data
        assert "vip_customers" in data
