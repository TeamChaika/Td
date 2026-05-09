"""Integration-тесты регистрации организации."""

from __future__ import annotations

from httpx import AsyncClient


class TestRegisterOrganization:
    """Тесты POST /api/v1/public/organizations/register."""

    async def test_successful_registration_returns_201(
        self, client: AsyncClient
    ) -> None:
        """Успешная регистрация возвращает 201."""
        resp = await client.post(
            "/api/v1/public/organizations/register",
            json={
                "email": "new-org@example.com",
                "password": "StrongPass123!",
                "first_name": "Иван",
                "last_name": "Иванов",
                "organization_name": "New Org",
                "organization_slug": "new-org",
                "accept_terms": True,
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "pending_moderation"
        assert "organization_id" in body
        assert "user_id" in body
        assert body["message"] == "Заявка отправлена на модерацию, мы свяжемся с вами"

    async def test_duplicate_email_returns_409(self, client: AsyncClient) -> None:
        """Повторная регистрация с тем же email возвращает 409."""
        payload = {
            "email": "dup-email@example.com",
            "password": "StrongPass123!",
            "first_name": "Иван",
            "last_name": "Иванов",
            "organization_name": "First Org",
            "organization_slug": "first-org",
            "accept_terms": True,
        }
        resp1 = await client.post("/api/v1/public/organizations/register", json=payload)
        assert resp1.status_code == 201

        payload["organization_slug"] = "second-org"
        resp2 = await client.post("/api/v1/public/organizations/register", json=payload)
        assert resp2.status_code == 409
        error = resp2.json()["error"]
        assert error["code"] == "email_taken"

    async def test_duplicate_slug_returns_409(self, client: AsyncClient) -> None:
        """Повторная регистрация с тем же slug возвращает 409."""
        payload = {
            "email": "slug1@example.com",
            "password": "StrongPass123!",
            "first_name": "Иван",
            "last_name": "Иванов",
            "organization_name": "Slug Org",
            "organization_slug": "duplicate-slug",
            "accept_terms": True,
        }
        resp1 = await client.post("/api/v1/public/organizations/register", json=payload)
        assert resp1.status_code == 201

        payload["email"] = "slug2@example.com"
        resp2 = await client.post("/api/v1/public/organizations/register", json=payload)
        assert resp2.status_code == 409
        error = resp2.json()["error"]
        assert error["code"] == "slug_taken"

    async def test_reserved_slug_returns_422(self, client: AsyncClient) -> None:
        """Зарезервированный slug возвращает ошибку валидации."""
        resp = await client.post(
            "/api/v1/public/organizations/register",
            json={
                "email": "reserved@example.com",
                "password": "StrongPass123!",
                "first_name": "Иван",
                "last_name": "Иванов",
                "organization_name": "Admin Org",
                "organization_slug": "admin",
                "accept_terms": True,
            },
        )
        assert resp.status_code == 400
        error = resp.json()["error"]
        assert error["code"] == "slug_invalid"

    async def test_invalid_slug_format_returns_error(self, client: AsyncClient) -> None:
        """Невалидный формат slug возвращает ошибку валидации."""
        resp = await client.post(
            "/api/v1/public/organizations/register",
            json={
                "email": "bad-slug@example.com",
                "password": "StrongPass123!",
                "first_name": "Иван",
                "last_name": "Иванов",
                "organization_name": "Bad Slug Org",
                "organization_slug": "AB-CD",
                "accept_terms": True,
            },
        )
        assert resp.status_code == 400
        error = resp.json()["error"]
        assert error["code"] == "slug_invalid"

    async def test_weak_password_returns_error(self, client: AsyncClient) -> None:
        """Слабый пароль возвращает ошибку валидации."""
        resp = await client.post(
            "/api/v1/public/organizations/register",
            json={
                "email": "weak@example.com",
                "password": "short",
                "first_name": "Иван",
                "last_name": "Иванов",
                "organization_name": "Weak Pass Org",
                "organization_slug": "weak-pass-org",
                "accept_terms": True,
            },
        )
        assert resp.status_code == 400
        error = resp.json()["error"]
        assert error["code"] == "validation_error"

    async def test_missing_accept_terms_returns_error(
        self, client: AsyncClient
    ) -> None:
        """Отсутствие accept_terms возвращает ошибку валидации."""
        resp = await client.post(
            "/api/v1/public/organizations/register",
            json={
                "email": "no-terms@example.com",
                "password": "StrongPass123!",
                "first_name": "Иван",
                "last_name": "Иванов",
                "organization_name": "No Terms Org",
                "organization_slug": "no-terms-org",
                "accept_terms": False,
            },
        )
        assert resp.status_code == 400
        error = resp.json()["error"]
        assert error["code"] == "validation_error"

    async def test_invalid_email_format_returns_error(
        self, client: AsyncClient
    ) -> None:
        """Невалидный формат email возвращает ошибку валидации."""
        resp = await client.post(
            "/api/v1/public/organizations/register",
            json={
                "email": "not-an-email",
                "password": "StrongPass123!",
                "first_name": "Иван",
                "last_name": "Иванов",
                "organization_name": "Bad Email Org",
                "organization_slug": "bad-email-org",
                "accept_terms": True,
            },
        )
        assert resp.status_code == 400
        error = resp.json()["error"]
        assert error["code"] == "validation_error"
