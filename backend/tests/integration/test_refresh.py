"""Integration-тесты refresh token."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestRefresh:
    """Тесты POST /api/v1/auth/refresh."""

    @pytest.fixture(autouse=True)
    async def _setup(self, organizer_user) -> None:
        """Гарантируем что тестовый пользователь создан."""
        pass

    async def test_valid_refresh_returns_200(self, client: AsyncClient) -> None:
        """Валидный refresh-токен возвращает 200 с новыми токенами."""
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "organizer@test-org.example.com",
                "password": "Organizer123!",
            },
        )
        assert login_resp.status_code == 200
        old_access = login_resp.json()["access_token"]

        refresh_resp = await client.post(
            "/api/v1/auth/refresh",
            cookies=login_resp.cookies,
        )
        assert refresh_resp.status_code == 200
        body = refresh_resp.json()
        assert "access_token" in body
        assert body["access_token"] != old_access
        assert "tdpay_refresh" in refresh_resp.cookies

    async def test_refresh_without_cookie_returns_401(
        self, client: AsyncClient
    ) -> None:
        """Refresh без cookie возвращает 401."""
        resp = await client.post("/api/v1/auth/refresh")
        assert resp.status_code == 401

    async def test_double_refresh_same_token_fails(self, client: AsyncClient) -> None:
        """Повторный refresh с тем же токеном падает (rotating refresh)."""
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "organizer@test-org.example.com",
                "password": "Organizer123!",
            },
        )
        assert login_resp.status_code == 200

        refresh1 = await client.post(
            "/api/v1/auth/refresh",
            cookies=login_resp.cookies,
        )
        assert refresh1.status_code == 200

        refresh2 = await client.post(
            "/api/v1/auth/refresh",
            cookies=login_resp.cookies,
        )
        assert refresh2.status_code == 401

    async def test_refresh_with_invalid_token_returns_401(
        self, client: AsyncClient
    ) -> None:
        """Refresh с невалидным токеном возвращает 401."""
        resp = await client.post(
            "/api/v1/auth/refresh",
            cookies={"tdpay_refresh": "invalid-token"},
        )
        assert resp.status_code == 401
