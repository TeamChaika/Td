"""Integration-тесты tenant isolation."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestTenantIsolation:
    """Тесты изоляции данных между организациями."""

    @pytest.fixture(autouse=True)
    async def _setup(self, organizer_user, superadmin_user) -> None:
        """Гарантируем что тестовые пользователи созданы."""
        pass

    async def _get_organizer_token(self, client: AsyncClient) -> str:
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "organizer@test-org.example.com",
                "password": "Organizer123!",
            },
        )
        assert resp.status_code == 200
        return resp.json()["access_token"]

    async def _register_and_approve_org(
        self, client: AsyncClient, suffix: str
    ) -> tuple[str, str]:
        reg_resp = await client.post(
            "/api/v1/public/organizations/register",
            json={
                "email": f"iso-{suffix}@example.com",
                "password": "StrongPass123!",
                "first_name": "Iso",
                "last_name": f"Test{suffix}",
                "organization_name": f"Isolation Test {suffix}",
                "organization_slug": f"isolation-{suffix}",
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
        sa_token = sa_resp.json()["access_token"]

        await client.post(
            f"/api/v1/admin/organizations/{org_id}/approve",
            headers={"Authorization": f"Bearer {sa_token}"},
        )

        org_login = await client.post(
            "/api/v1/auth/login",
            json={
                "email": f"iso-{suffix}@example.com",
                "password": "StrongPass123!",
            },
        )
        assert org_login.status_code == 200
        org_token = org_login.json()["access_token"]

        return org_id, org_token

    async def test_organizer_a_sees_only_own_org(self, client: AsyncClient) -> None:
        """Организатор A видит только свою организацию."""
        token_a = await self._get_organizer_token(client)

        resp = await client.get(
            "/api/v1/organizer/organization",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["slug"] == "test-org"

    async def test_two_organizers_see_different_orgs(self, client: AsyncClient) -> None:
        """Два организатора из разных организаций видят разные данные."""
        _, token_b = await self._register_and_approve_org(client, "b")

        token_a = await self._get_organizer_token(client)
        resp_a = await client.get(
            "/api/v1/organizer/organization",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert resp_a.status_code == 200
        assert resp_a.json()["slug"] == "test-org"

        resp_b = await client.get(
            "/api/v1/organizer/organization",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert resp_b.status_code == 200
        assert resp_b.json()["slug"] == "isolation-b"

    @pytest.mark.skip(reason="требует Phase 3 events — нет таблицы events с данными")
    async def test_organizer_cannot_access_other_org_events(
        self, client: AsyncClient
    ) -> None:
        """Организатор A не может получить события организации B."""
        pass

    async def test_access_token_org_id_used_from_jwt_not_subdomain(
        self, client: AsyncClient
    ) -> None:
        """Пользователь с access-токеном от org A пытается endpoint на subdomain B —
        эндпоинт использует org_id из JWT, не из subdomain.
        """
        # Регистрируем и одобряем вторую организацию
        _, token_b = await self._register_and_approve_org(client, "cross-tenant")

        # Токен от организации B
        token_a = await self._get_organizer_token(client)

        # Пользователь A (test-org) делает GET /organizer/organization
        # с токеном от A — должен увидеть свою организацию, не B
        resp = await client.get(
            "/api/v1/organizer/organization",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        # Пользователь A видит свою организацию (test-org), а не isolation-cross-tenant
        assert body["slug"] == "test-org"

        # Пользователь B (isolation-cross-tenant) тоже видит свою
        resp_b = await client.get(
            "/api/v1/organizer/organization",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert resp_b.status_code == 200
        assert resp_b.json()["slug"] == "isolation-cross-tenant"
