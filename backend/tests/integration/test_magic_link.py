"""Integration-тесты magic-link flow."""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient


class TestMagicLink:
    """Тесты POST /api/v1/auth/magic-link/request и /verify."""

    @pytest.fixture(autouse=True)
    async def _setup(self, organizer_user) -> None:
        """Гарантируем что тестовый пользователь создан."""
        pass

    async def test_request_always_returns_202(self, client: AsyncClient) -> None:
        """Запрос magic-link всегда возвращает 202 (user enumeration protection)."""
        resp = await client.post(
            "/api/v1/auth/magic-link/request",
            json={"email": "organizer@test-org.example.com"},
        )
        assert resp.status_code == 202
        assert resp.json() == {"status": "accepted"}

        resp = await client.post(
            "/api/v1/auth/magic-link/request",
            json={"email": "no-such-user@example.com"},
        )
        assert resp.status_code == 202
        assert resp.json() == {"status": "accepted"}

    async def test_request_creates_redis_key_for_existing_user(
        self, client: AsyncClient, fake_redis
    ) -> None:
        """Для существующего пользователя в Redis создаётся ключ magic:{token}."""
        await fake_redis.flushall()

        resp = await client.post(
            "/api/v1/auth/magic-link/request",
            json={"email": "organizer@test-org.example.com"},
        )
        assert resp.status_code == 202

        keys = await fake_redis.keys("magic:*")
        assert len(keys) == 1
        key = keys[0]

        raw = await fake_redis.get(key)
        payload = json.loads(raw)
        assert payload["email"] == "organizer@test-org.example.com"
        assert "user_id" in payload

        ttl = await fake_redis.ttl(key)
        assert 0 < ttl <= 900

    async def test_verify_valid_token_returns_200(
        self, client: AsyncClient, fake_redis
    ) -> None:
        """Валидный magic-link токен возвращает 200 с токенами."""
        await fake_redis.flushall()

        await client.post(
            "/api/v1/auth/magic-link/request",
            json={"email": "organizer@test-org.example.com"},
        )

        keys = await fake_redis.keys("magic:*")
        assert len(keys) == 1
        token = keys[0].replace("magic:", "")

        resp = await client.post(
            "/api/v1/auth/magic-link/verify",
            json={"token": token},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert "tdpay_refresh" in resp.cookies

        keys_after = await fake_redis.keys("magic:*")
        assert len(keys_after) == 0

    async def test_verify_invalid_token_returns_401(self, client: AsyncClient) -> None:
        """Невалидный токен возвращает 401."""
        resp = await client.post(
            "/api/v1/auth/magic-link/verify",
            json={"token": "invalid-token-that-does-not-exist"},
        )
        assert resp.status_code == 401
        error = resp.json()["error"]
        assert error["code"] == "invalid_magic_link"

    async def test_verify_used_token_returns_401(
        self, client: AsyncClient, fake_redis
    ) -> None:
        """Повторное использование токена возвращает 401."""
        await fake_redis.flushall()

        await client.post(
            "/api/v1/auth/magic-link/request",
            json={"email": "organizer@test-org.example.com"},
        )

        keys = await fake_redis.keys("magic:*")
        token = keys[0].replace("magic:", "")

        resp1 = await client.post(
            "/api/v1/auth/magic-link/verify",
            json={"token": token},
        )
        assert resp1.status_code == 200

        resp2 = await client.post(
            "/api/v1/auth/magic-link/verify",
            json={"token": token},
        )
        assert resp2.status_code == 401
        error = resp2.json()["error"]
        assert error["code"] == "invalid_magic_link"
