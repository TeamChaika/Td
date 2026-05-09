"""Integration-тесты админских эндпоинтов событий (superadmin).

Проверяет модерацию: список pending, publish, reject.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from paytools.db.models.enums import EventStatus, OrganizationStatus
from paytools.db.models.organization import Organization
from paytools.db.repositories.event import EventRepository
from paytools.db.repositories.organization import OrganizationRepository
from paytools.db.repositories.user import UserRepository
from paytools.domain.events.service import CreateEventInput, EventService

# ---------------------------------------------------------------------------
# Хелперы
# ---------------------------------------------------------------------------


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


async def _get_test_org(session: AsyncSession) -> Organization:
    user_repo = UserRepository(session)
    user = await user_repo.get_by_email("organizer@test-org.example.com")
    org_repo = OrganizationRepository(session)
    return await org_repo.get_by_id(user.organization_id)


async def _create_event(
    session: AsyncSession,
    org: Organization,
    *,
    title: str = "Test Event",
    status: EventStatus = EventStatus.DRAFT,
) -> str:
    """Создать событие и вернуть его ID (строкой)."""
    svc = EventService(
        session,
        event_repo=EventRepository(session),
        org_repo=OrganizationRepository(session),
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
        await session.flush()
    return str(event.id)


async def _create_other_org(session: AsyncSession, slug: str) -> Organization:
    """Создать ещё одну активную организацию."""
    org = Organization(id=uuid4(), slug=slug, name=f"Org {slug}", status=OrganizationStatus.ACTIVE)
    session.add(org)
    await session.flush()
    return org


# ---------------------------------------------------------------------------
# Тесты
# ---------------------------------------------------------------------------


class TestAdminEvents:
    """Тесты админских эндпоинтов событий."""

    @pytest.fixture(autouse=True)
    async def _setup(self, organizer_user, superadmin_user) -> None:
        """Гарантируем что тестовые пользователи созданы."""
        pass

    # --- Список на модерации ---

    async def test_list_pending_from_all_orgs(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """GET /admin/events возвращает pending события со всех организаций."""
        sa_token = await _get_superadmin_token(client)
        org_a = await _get_test_org(async_session)
        org_b = await _create_other_org(async_session, "admin-org-b")

        # Создаём события в разных статусах в обеих организациях
        await _create_event(async_session, org_a, title="Draft A", status=EventStatus.DRAFT)
        await _create_event(async_session, org_a, title="Pending A", status=EventStatus.PENDING_MODERATION)
        await _create_event(async_session, org_a, title="Published A", status=EventStatus.PUBLISHED)
        await _create_event(async_session, org_b, title="Draft B", status=EventStatus.DRAFT)
        await _create_event(async_session, org_b, title="Pending B", status=EventStatus.PENDING_MODERATION)

        resp = await client.get(
            "/api/v1/admin/events",
            headers={"Authorization": f"Bearer {sa_token}"},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        # Только pending_moderation, со всех org
        titles = {item["title"] for item in items}
        assert titles == {"Pending A", "Pending B"}

    async def test_admin_endpoints_require_superadmin(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """Без токена → 401, с organizer токеном → 403."""
        # Без токена
        resp_no_auth = await client.get("/api/v1/admin/events")
        assert resp_no_auth.status_code == 401

        # С organizer токеном
        org_token = await _get_organizer_token(client)
        resp_org = await client.get(
            "/api/v1/admin/events",
            headers={"Authorization": f"Bearer {org_token}"},
        )
        assert resp_org.status_code == 403

    # --- Publish ---

    async def test_publish_pending_event(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """POST /admin/events/{id}/publish: pending → published."""
        sa_token = await _get_superadmin_token(client)
        org = await _get_test_org(async_session)
        event_id = await _create_event(
            async_session, org, title="Publish Me", status=EventStatus.PENDING_MODERATION
        )

        resp = await client.post(
            f"/api/v1/admin/events/{event_id}/publish",
            headers={"Authorization": f"Bearer {sa_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "published"
        assert body["published_at"] is not None

    async def test_publish_already_published_fails(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """Повторный publish уже published → 409 (invalid transition)."""
        sa_token = await _get_superadmin_token(client)
        org = await _get_test_org(async_session)
        event_id = await _create_event(
            async_session, org, title="Already Pub", status=EventStatus.PUBLISHED
        )

        resp = await client.post(
            f"/api/v1/admin/events/{event_id}/publish",
            headers={"Authorization": f"Bearer {sa_token}"},
        )
        assert resp.status_code == 409

    async def test_publish_draft_fails(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """Нельзя publish из draft напрямую (только через pending)."""
        sa_token = await _get_superadmin_token(client)
        org = await _get_test_org(async_session)
        event_id = await _create_event(
            async_session, org, title="Draft Pub", status=EventStatus.DRAFT
        )

        resp = await client.post(
            f"/api/v1/admin/events/{event_id}/publish",
            headers={"Authorization": f"Bearer {sa_token}"},
        )
        assert resp.status_code == 409

    async def test_publish_by_organizer_returns_403(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """Organizer получает 403 при попытке publish через админский эндпоинт."""
        org_token = await _get_organizer_token(client)
        org = await _get_test_org(async_session)
        event_id = await _create_event(
            async_session, org, title="Org Pub", status=EventStatus.PENDING_MODERATION
        )

        resp = await client.post(
            f"/api/v1/admin/events/{event_id}/publish",
            headers={"Authorization": f"Bearer {org_token}"},
        )
        assert resp.status_code == 403

    # --- Reject ---

    async def test_reject_pending_event(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """POST /admin/events/{id}/reject: pending → rejected, note сохранён."""
        sa_token = await _get_superadmin_token(client)
        org = await _get_test_org(async_session)
        event_id = await _create_event(
            async_session, org, title="Reject Me", status=EventStatus.PENDING_MODERATION
        )

        resp = await client.post(
            f"/api/v1/admin/events/{event_id}/reject",
            json={"note": "Не соответствует требованиям"},
            headers={"Authorization": f"Bearer {sa_token}"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

        # Проверяем что статус изменился и note сохранён
        event_repo = EventRepository(async_session)
        from uuid import UUID
        event = await event_repo.get(UUID(event_id))
        assert event is not None
        assert event.status == EventStatus.REJECTED
        assert event.moderation_note == "Не соответствует требованиям"

    async def test_reject_requires_note(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """Отклонение без note → 422 (валидация Pydantic)."""
        sa_token = await _get_superadmin_token(client)
        org = await _get_test_org(async_session)
        event_id = await _create_event(
            async_session, org, title="Reject No Note", status=EventStatus.PENDING_MODERATION
        )

        resp = await client.post(
            f"/api/v1/admin/events/{event_id}/reject",
            json={"note": ""},  # пустая строка — не проходит min_length=3
            headers={"Authorization": f"Bearer {sa_token}"},
        )
        # validation_error_handler мапит 422 → 400
        assert resp.status_code == 400

    async def test_reject_published_fails(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """Нельзя reject уже published событие."""
        sa_token = await _get_superadmin_token(client)
        org = await _get_test_org(async_session)
        event_id = await _create_event(
            async_session, org, title="Pub Reject", status=EventStatus.PUBLISHED
        )

        resp = await client.post(
            f"/api/v1/admin/events/{event_id}/reject",
            json={"note": "Слишком поздно"},
            headers={"Authorization": f"Bearer {sa_token}"},
        )
        assert resp.status_code == 409

    async def test_reject_by_organizer_returns_403(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """Organizer получает 403 при попытке reject через админский эндпоинт."""
        org_token = await _get_organizer_token(client)
        org = await _get_test_org(async_session)
        event_id = await _create_event(
            async_session, org, title="Org Reject", status=EventStatus.PENDING_MODERATION
        )

        resp = await client.post(
            f"/api/v1/admin/events/{event_id}/reject",
            json={"note": "Не нравится"},
            headers={"Authorization": f"Bearer {org_token}"},
        )
        assert resp.status_code == 403