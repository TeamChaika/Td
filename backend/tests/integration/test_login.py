"""Integration-тесты логина."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestLogin:
    """Тесты POST /api/v1/auth/login."""

    @pytest.fixture(autouse=True)
    async def _setup(self, organizer_user, superadmin_user) -> None:
        """Гарантируем что тестовые пользователи созданы."""
        pass

    async def test_valid_login_returns_200_with_tokens(
        self, client: AsyncClient
    ) -> None:
        """Валидный логин возвращает 200 с access_token и refresh cookie."""
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "organizer@test-org.example.com",
                "password": "Organizer123!",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert body["expires_in"] > 0
        assert "tdpay_refresh" in resp.cookies

    async def test_wrong_password_returns_401(self, client: AsyncClient) -> None:
        """Неверный пароль возвращает 401."""
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "organizer@test-org.example.com",
                "password": "WrongPassword1!",
            },
        )
        assert resp.status_code == 401
        error = resp.json()["error"]
        assert error["code"] == "invalid_credentials"

    async def test_nonexistent_email_returns_401(self, client: AsyncClient) -> None:
        """Несуществующий email возвращает 401 (не 404)."""
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "no-such-user@example.com",
                "password": "AnyPassword1!",
            },
        )
        assert resp.status_code == 401
        error = resp.json()["error"]
        assert error["code"] == "invalid_credentials"

    async def test_pending_organization_returns_403(self, client: AsyncClient) -> None:
        """Организация в статусе pending_moderation возвращает 403."""
        reg_resp = await client.post(
            "/api/v1/public/organizations/register",
            json={
                "email": "pending-login@example.com",
                "password": "StrongPass123!",
                "first_name": "Test",
                "last_name": "User",
                "organization_name": "Pending Login Org",
                "organization_slug": "pending-login-org",
                "accept_terms": True,
            },
        )
        assert reg_resp.status_code == 201

        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "pending-login@example.com",
                "password": "StrongPass123!",
            },
        )
        assert resp.status_code == 403
        error = resp.json()["error"]
        assert error["code"] == "organization_pending"

    async def test_suspended_organization_returns_403(
        self, client: AsyncClient
    ) -> None:
        """Организация в статусе suspended возвращает 403."""
        reg_resp = await client.post(
            "/api/v1/public/organizations/register",
            json={
                "email": "suspended-login@example.com",
                "password": "StrongPass123!",
                "first_name": "Test",
                "last_name": "User",
                "organization_name": "Suspended Login Org",
                "organization_slug": "suspended-login-org",
                "accept_terms": True,
            },
        )
        assert reg_resp.status_code == 201
        org_id = reg_resp.json()["organization_id"]

        sa_resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "superadmin@tdpay.example.com",
                "password": "SuperAdmin123!",
            },
        )
        assert sa_resp.status_code == 200
        sa_token = sa_resp.json()["access_token"]

        await client.post(
            f"/api/v1/admin/organizations/{org_id}/approve",
            headers={"Authorization": f"Bearer {sa_token}"},
        )

        await client.post(
            f"/api/v1/admin/organizations/{org_id}/suspend",
            json={"reason": "Testing suspension"},
            headers={"Authorization": f"Bearer {sa_token}"},
        )

        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "suspended-login@example.com",
                "password": "StrongPass123!",
            },
        )
        assert resp.status_code == 403
        error = resp.json()["error"]
        assert error["code"] == "organization_suspended"
