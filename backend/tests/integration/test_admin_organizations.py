"""Integration-тесты админских эндпоинтов организаций."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestAdminOrganizations:
    """Тесты POST /api/v1/admin/organizations/{id}/approve и /suspend."""

    @pytest.fixture(autouse=True)
    async def _setup(self, organizer_user, superadmin_user) -> None:
        """Гарантируем что тестовые пользователи созданы."""
        pass

    async def _get_superadmin_token(self, client: AsyncClient) -> str:
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "superadmin@tdpay.example.com",
                "password": "SuperAdmin123!",
            },
        )
        assert resp.status_code == 200
        return resp.json()["access_token"]

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

    async def _register_org(self, client: AsyncClient, suffix: str) -> str:
        resp = await client.post(
            "/api/v1/public/organizations/register",
            json={
                "email": f"admin-test-{suffix}@example.com",
                "password": "StrongPass123!",
                "first_name": "Test",
                "last_name": "Admin",
                "organization_name": f"Admin Test Org {suffix}",
                "organization_slug": f"admin-test-{suffix}",
                "accept_terms": True,
            },
        )
        assert resp.status_code == 201
        return resp.json()["organization_id"]

    async def test_approve_by_superadmin_returns_200(self, client: AsyncClient) -> None:
        """Superadmin может одобрить организацию."""
        org_id = await self._register_org(client, "approve")
        sa_token = await self._get_superadmin_token(client)

        resp = await client.post(
            f"/api/v1/admin/organizations/{org_id}/approve",
            headers={"Authorization": f"Bearer {sa_token}"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

        list_resp = await client.get(
            "/api/v1/admin/organizations",
            headers={"Authorization": f"Bearer {sa_token}"},
        )
        assert list_resp.status_code == 200
        items = list_resp.json()["items"]
        org = next((o for o in items if o["id"] == org_id), None)
        assert org is not None
        assert org["status"] == "active"

    async def test_approve_by_organizer_returns_403(self, client: AsyncClient) -> None:
        """Organizer не может одобрить организацию."""
        org_id = await self._register_org(client, "approve-denied")
        org_token = await self._get_organizer_token(client)

        resp = await client.post(
            f"/api/v1/admin/organizations/{org_id}/approve",
            headers={"Authorization": f"Bearer {org_token}"},
        )
        assert resp.status_code == 403
        error = resp.json()["error"]
        assert error["code"] == "insufficient_role"

    async def test_approve_nonexistent_org_returns_404(
        self, client: AsyncClient
    ) -> None:
        """Одобрение несуществующей организации возвращает 404."""
        sa_token = await self._get_superadmin_token(client)

        resp = await client.post(
            "/api/v1/admin/organizations/00000000-0000-0000-0000-000000000000/approve",
            headers={"Authorization": f"Bearer {sa_token}"},
        )
        assert resp.status_code == 404

    async def test_suspend_by_superadmin_returns_200(self, client: AsyncClient) -> None:
        """Superadmin может заблокировать организацию."""
        org_id = await self._register_org(client, "suspend")
        sa_token = await self._get_superadmin_token(client)

        await client.post(
            f"/api/v1/admin/organizations/{org_id}/approve",
            headers={"Authorization": f"Bearer {sa_token}"},
        )

        resp = await client.post(
            f"/api/v1/admin/organizations/{org_id}/suspend",
            json={"reason": "Нарушение правил платформы"},
            headers={"Authorization": f"Bearer {sa_token}"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    async def test_suspend_by_organizer_returns_403(self, client: AsyncClient) -> None:
        """Organizer не может заблокировать организацию."""
        org_id = await self._register_org(client, "suspend-denied")
        sa_token = await self._get_superadmin_token(client)
        org_token = await self._get_organizer_token(client)

        await client.post(
            f"/api/v1/admin/organizations/{org_id}/approve",
            headers={"Authorization": f"Bearer {sa_token}"},
        )

        resp = await client.post(
            f"/api/v1/admin/organizations/{org_id}/suspend",
            json={"reason": "Нарушение"},
            headers={"Authorization": f"Bearer {org_token}"},
        )
        assert resp.status_code == 403
        error = resp.json()["error"]
        assert error["code"] == "insufficient_role"

    async def test_list_organizations_returns_paginated(
        self, client: AsyncClient
    ) -> None:
        """GET /admin/organizations возвращает пагинированный список."""
        sa_token = await self._get_superadmin_token(client)

        resp = await client.get(
            "/api/v1/admin/organizations",
            headers={"Authorization": f"Bearer {sa_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert "pagination" in body
        assert body["pagination"]["page"] == 1
