"""Integration-тест: logout ревокает access-токен.

После logout запрос с тем же access-токеном должен получить 401.
"""

from __future__ import annotations

from httpx import AsyncClient


class TestLogoutRevokesAccess:
    """Проверка, что после logout access-токен больше не работает."""

    async def test_logout_revokes_access_token(
        self, client: AsyncClient, organizer_user
    ) -> None:
        """После logout запрос с тем же access-токеном получает 401."""
        # 1. Логинимся — получаем access + refresh (cookie)
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "organizer@test-org.example.com",
                "password": "Organizer123!",
            },
        )
        assert login_resp.status_code == 200
        access_token = login_resp.json()["access_token"]
        auth = {"Authorization": f"Bearer {access_token}"}

        # 2. Проверяем, что access-токен работает
        me_resp = await client.get("/api/v1/auth/me", headers=auth)
        assert me_resp.status_code == 200

        # 3. Logout — передаём access-токен в Authorization и refresh в cookie
        logout_resp = await client.post(
            "/api/v1/auth/logout",
            headers=auth,
            cookies=login_resp.cookies,
        )
        assert logout_resp.status_code == 204

        # 4. Тот же access-токен должен возвращать 401
        me_after = await client.get("/api/v1/auth/me", headers=auth)
        assert me_after.status_code == 401

    async def test_logout_without_access_header_still_clears_cookie(
        self, client: AsyncClient, organizer_user
    ) -> None:
        """Logout без Authorization header всё равно очищает cookie."""
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "organizer@test-org.example.com",
                "password": "Organizer123!",
            },
        )
        assert login_resp.status_code == 200

        # Logout без access-токена
        logout_resp = await client.post(
            "/api/v1/auth/logout",
            cookies=login_resp.cookies,
        )
        assert logout_resp.status_code == 204

        # Refresh больше не работает (refresh был ревокнут)
        refresh_resp = await client.post(
            "/api/v1/auth/refresh",
            cookies=login_resp.cookies,
        )
        assert refresh_resp.status_code == 401

    async def test_logout_with_expired_access_token(
        self, client: AsyncClient, organizer_user
    ) -> None:
        """Logout с истёкшим access-токеном всё равно ревокает refresh и чистит cookie."""
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "organizer@test-org.example.com",
                "password": "Organizer123!",
            },
        )
        assert login_resp.status_code == 200

        # Logout с заведомо невалидным access-токеном
        logout_resp = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": "Bearer expired.invalid.token"},
            cookies=login_resp.cookies,
        )
        assert logout_resp.status_code == 204

        # Refresh больше не работает
        refresh_resp = await client.post(
            "/api/v1/auth/refresh",
            cookies=login_resp.cookies,
        )
        assert refresh_resp.status_code == 401
