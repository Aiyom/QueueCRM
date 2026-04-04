"""Tests for authentication endpoints."""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestLogin:
    async def test_login_success(self, client: AsyncClient, sample_admin):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": sample_admin.email, "password": "password123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client: AsyncClient, sample_admin):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": sample_admin.email, "password": "wrongpass"},
        )
        assert resp.status_code == 401

    async def test_login_unknown_email(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@test.com", "password": "password123"},
        )
        assert resp.status_code == 401

    async def test_login_inactive_user(self, client: AsyncClient, db_session, sample_admin):
        sample_admin.is_active = False
        await db_session.flush()

        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": sample_admin.email, "password": "password123"},
        )
        assert resp.status_code == 403

    async def test_super_admin_login(self, client: AsyncClient, sample_super_admin):
        resp = await client.post(
            "/api/v1/auth/super-admin/login",
            json={"email": sample_super_admin.email, "password": "supersecret"},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()


class TestRefresh:
    async def test_refresh_returns_new_tokens(self, client: AsyncClient, sample_admin):
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": sample_admin.email, "password": "password123"},
        )
        assert login.status_code == 200
        refresh_token = login.json()["refresh_token"]

        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

        # Old refresh token is now revoked
        resp2 = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp2.status_code == 401

    async def test_refresh_invalid_token(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "not.a.token"},
        )
        assert resp.status_code == 401


class TestLogout:
    async def test_logout_revokes_token(self, client: AsyncClient, sample_admin):
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": sample_admin.email, "password": "password123"},
        )
        assert login.status_code == 200
        tokens = login.json()

        resp = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert resp.status_code == 200

        # Refresh must now fail
        resp2 = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert resp2.status_code == 401

    async def test_logout_idempotent(self, client: AsyncClient, sample_admin):
        """Logout twice returns 200 both times."""
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": sample_admin.email, "password": "password123"},
        )
        token = login.json()["refresh_token"]

        for _ in range(2):
            resp = await client.post(
                "/api/v1/auth/logout", json={"refresh_token": token}
            )
            assert resp.status_code == 200

    async def test_logout_garbage_token(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/logout", json={"refresh_token": "garbage"}
        )
        assert resp.status_code == 200  # always 200


class TestMe:
    async def test_me_staff(self, client: AsyncClient, admin_headers, sample_admin):
        resp = await client.get("/api/v1/auth/me", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == sample_admin.email
        assert data["role"] == "admin"
        assert data["tenant_id"] is not None

    async def test_me_super_admin(
        self, client: AsyncClient, super_admin_headers, sample_super_admin
    ):
        resp = await client.get("/api/v1/auth/me", headers=super_admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "super_admin"
        assert data["tenant_id"] is None

    async def test_me_no_token(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401
