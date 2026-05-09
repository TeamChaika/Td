"""Integration-тесты organizer events API.

Использует реальный TestClient с переопределёнными зависимостями.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient

from paytools.db.models.enums import EventStatus, OrganizationStatus, UserRole
from paytools.db.models.organization import Organization
from paytools.db.models.user import User
from paytools.db.repositories.event import EventRepository
from paytools.db.repositories.organization import OrganizationRepository
from paytools.db.repositories.user import UserRepository
from paytools.domain.events.service import CreateEventInput, EventService


async def _get_organizer_token(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "organizer@test-org.example.com",
            "password": "Organizer123!",
        },
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def _get_superadmin_token(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "superadmin@tdpay.example.com",
            "password": "SuperAdmin123!",
        },
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def _create_event_via_service(
    client: AsyncClient,
    async_session,
    org: Organization,
    status: EventStatus = EventStatus.DRAFT,
    title: str = "Test Event",
) -> str:
    """Создать событие через доменный сервис напрямую."""
    svc = EventService(
        async_session,
        event_repo=EventRepository(async_session),
        org_repo=OrganizationRepository(async_session),
    )
    event = await svc.create(
        org.id,
        CreateEventInput(
            title=title,
            slug=None,
            schedule={
                "type": "single",
                "starts_at": "2026-12-31T20:00:00+03:00",
                "ends_at": "2027-01-01T03:00:00+03:00",
            },
            capacity_policy={"type": "unlimited"},
        ),
    )
    if status != EventStatus.DRAFT:
        event.status = status
        await async_session.flush()
    return str(event.id)


class TestOrganizerEventsCRUD:
    """Тесты CRUD событий организатора."""

    @pytest.fixture(autouse=True)
    async def _setup(self, organizer_user, superadmin_user) -> None:
        """Гарантируем что тестовые пользователи созданы."""
        pass

    async def test_create_event_returns_draft(
        self, client: AsyncClient, async_session
    ) -> None:
        """POST /organizer/events создаёт событие в статусе draft."""
        token = await _get_organizer_token(client)

        resp = await client.post(
            "/api/v1/organizer/events",
            json={
                "title": "E2E Test Event",
                "schedule": {
                    "type": "single",
                    "starts_at": "2026-12-31T20:00:00+03:00",
                    "ends_at": "2027-01-01T03:00:00+03:00",
                },
                "capacity_policy": {"type": "unlimited"},
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "draft"
        assert body["title"] == "E2E Test Event"
        assert body["slug"] is not None

    async def test_list_events_returns_only_own(
        self, client: AsyncClient, async_session
    ) -> None:
        """GET /organizer/events возвращает только события своей организации."""
        token = await _get_organizer_token(client)

        # Получаем организацию пользователя
        user_repo = UserRepository(async_session)
        user = await user_repo.get_by_email("organizer@test-org.example.com")
        org_repo = OrganizationRepository(async_session)
        org = await org_repo.get_by_id(user.organization_id)

        # Создаём событие через сервис
        await _create_event_via_service(client, async_session, org, title="My Event")

        # Создаём другую организацию с событием
        other_org = Organization(
            id=uuid4(), slug="other-org", name="Other", status=OrganizationStatus.ACTIVE
        )
        async_session.add(other_org)
        await async_session.flush()
        await _create_event_via_service(client, async_session, other_org, title="Other Event")

        resp = await client.get(
            "/api/v1/organizer/events",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        items = body["items"]
        # Должны видеть только своё событие
        assert len(items) == 1
        assert items[0]["title"] == "My Event"

    async def test_get_event_by_id_returns_200(
        self, client: AsyncClient, async_session
    ) -> None:
        """GET /organizer/events/{id} возвращает событие."""
        token = await _get_organizer_token(client)

        user_repo = UserRepository(async_session)
        user = await user_repo.get_by_email("organizer@test-org.example.com")
        org_repo = OrganizationRepository(async_session)
        org = await org_repo.get_by_id(user.organization_id)

        event_id = await _create_event_via_service(
            client, async_session, org, title="Detail Event"
        )

        resp = await client.get(
            f"/api/v1/organizer/events/{event_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "Detail Event"
        assert body["status"] == "draft"
        assert "tariffs" in body

    async def test_get_event_other_org_returns_403(
        self, client: AsyncClient, async_session
    ) -> None:
        """GET события другой организации возвращает 403."""
        token = await _get_organizer_token(client)

        # Создаём другую организацию с событием
        other_org = Organization(
            id=uuid4(), slug="other-org-2", name="Other 2", status=OrganizationStatus.ACTIVE
        )
        async_session.add(other_org)
        await async_session.flush()

        event_id = await _create_event_via_service(
            client, async_session, other_org, title="Other Event"
        )

        resp = await client.get(
            f"/api/v1/organizer/events/{event_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        # Должен быть 403 или 404 (tenant isolation)
        assert resp.status_code in (403, 404)

    async def test_patch_event_in_draft_updates_fields(
        self, client: AsyncClient, async_session
    ) -> None:
        """PATCH события в draft обновляет поля."""
        token = await _get_organizer_token(client)

        user_repo = UserRepository(async_session)
        user = await user_repo.get_by_email("organizer@test-org.example.com")
        org_repo = OrganizationRepository(async_session)
        org = await org_repo.get_by_id(user.organization_id)

        event_id = await _create_event_via_service(
            client, async_session, org, title="Original Title"
        )

        resp = await client.patch(
            f"/api/v1/organizer/events/{event_id}",
            json={"title": "Updated Title", "description_md": "New description"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "Updated Title"
        assert body["description_md"] == "New description"

    async def test_delete_event_archives(
        self, client: AsyncClient, async_session
    ) -> None:
        """DELETE /organizer/events/{id} архивирует событие."""
        token = await _get_organizer_token(client)

        user_repo = UserRepository(async_session)
        user = await user_repo.get_by_email("organizer@test-org.example.com")
        org_repo = OrganizationRepository(async_session)
        org = await org_repo.get_by_id(user.organization_id)

        event_id = await _create_event_via_service(
            client, async_session, org, title="To Archive"
        )

        resp = await client.delete(
            f"/api/v1/organizer/events/{event_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

        # Проверяем что статус archived
        event_repo = EventRepository(async_session)
        event = await event_repo.get(uuid4())  # не найдём — используем прямой запрос
        # Используем API для проверки
        get_resp = await client.get(
            f"/api/v1/organizer/events/{event_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["status"] == "archived"

    async def test_submit_event_changes_status(
        self, client: AsyncClient, async_session
    ) -> None:
        """POST /organizer/events/{id}/submit меняет статус на pending_moderation."""
        token = await _get_organizer_token(client)

        user_repo = UserRepository(async_session)
        user = await user_repo.get_by_email("organizer@test-org.example.com")
        org_repo = OrganizationRepository(async_session)
        org = await org_repo.get_by_id(user.organization_id)

        event_id = await _create_event_via_service(
            client, async_session, org, title="Submit Me"
        )

        resp = await client.post(
            f"/api/v1/organizer/events/{event_id}/submit",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending_moderation"

    async def test_publish_event_by_organizer_without_auto_publish_returns_403(
        self, client: AsyncClient, async_session
    ) -> None:
        """Organizer без auto_publish_enabled получает 403 при publish."""
        token = await _get_organizer_token(client)

        user_repo = UserRepository(async_session)
        user = await user_repo.get_by_email("organizer@test-org.example.com")
        org_repo = OrganizationRepository(async_session)
        org = await org_repo.get_by_id(user.organization_id)

        # test-org имеет auto_publish_enabled=False по умолчанию
        event_id = await _create_event_via_service(
            client, async_session, org,
            title="Cannot Publish",
            status=EventStatus.PENDING_MODERATION,
        )

        resp = await client.post(
            f"/api/v1/organizer/events/{event_id}/publish",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403


class TestOrganizerTariffsCRUD:
    """Тесты CRUD тарифов."""

    @pytest.fixture(autouse=True)
    async def _setup(self, organizer_user, superadmin_user) -> None:
        """Гарантируем что тестовые пользователи созданы."""
        pass

    async def _setup_event(
        self, client: AsyncClient, async_session
    ) -> tuple[str, str]:
        """Создать событие и вернуть (token, event_id)."""
        token = await _get_organizer_token(client)
        user_repo = UserRepository(async_session)
        user = await user_repo.get_by_email("organizer@test-org.example.com")
        org_repo = OrganizationRepository(async_session)
        org = await org_repo.get_by_id(user.organization_id)
        event_id = await _create_event_via_service(
            client, async_session, org, title="Event With Tariffs"
        )
        return token, event_id

    async def test_create_tariff_for_event(
        self, client: AsyncClient, async_session
    ) -> None:
        """POST /organizer/events/{event_id}/tariffs создаёт тариф."""
        token, event_id = await self._setup_event(client, async_session)

        resp = await client.post(
            f"/api/v1/organizer/events/{event_id}/tariffs",
            json={
                "name": "VIP",
                "price_kopecks": 500000,
                "capacity_limit": 50,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "VIP"
        assert body["price_kopecks"] == 500000
        assert body["capacity_limit"] == 50

    async def test_list_tariffs_for_event(
        self, client: AsyncClient, async_session
    ) -> None:
        """GET /organizer/events/{event_id}/tariffs возвращает список тарифов."""
        token, event_id = await self._setup_event(client, async_session)

        # Создаём тариф
        await client.post(
            f"/api/v1/organizer/events/{event_id}/tariffs",
            json={"name": "Standard", "price_kopecks": 200000},
            headers={"Authorization": f"Bearer {token}"},
        )

        resp = await client.get(
            f"/api/v1/organizer/events/{event_id}/tariffs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["name"] == "Standard"

    async def test_delete_tariff_hard_if_not_sold(
        self, client: AsyncClient, async_session
    ) -> None:
        """DELETE тарифа без продаж делает hard-delete."""
        token, event_id = await self._setup_event(client, async_session)

        create_resp = await client.post(
            f"/api/v1/organizer/events/{event_id}/tariffs",
            json={"name": "To Delete", "price_kopecks": 100000},
            headers={"Authorization": f"Bearer {token}"},
        )
        tariff_id = create_resp.json()["id"]

        resp = await client.delete(
            f"/api/v1/organizer/tariffs/{tariff_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["method"] == "hard"

        # Проверяем что тариф удалён
        list_resp = await client.get(
            f"/api/v1/organizer/events/{event_id}/tariffs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert len(list_resp.json()) == 0