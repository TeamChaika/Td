"""Integration-тесты публичных эндпоинтов событий.

Использует X-Tenant-Slug заголовок для эмуляции subdomain.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from paytools.db.models.enums import EventStatus, OrganizationStatus
from paytools.db.models.event import Event, Tariff
from paytools.db.models.organization import Organization
from paytools.db.repositories.event import EventRepository
from paytools.db.repositories.organization import OrganizationRepository
from paytools.db.repositories.user import UserRepository
from paytools.domain.events.service import CreateEventInput, EventService

# Slug тестовой организации из conftest
TEST_ORG_SLUG = "test-org"


# ---------------------------------------------------------------------------
# Хелперы
# ---------------------------------------------------------------------------


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


async def _create_event_in_org(
    session: AsyncSession,
    org: Organization,
    *,
    title: str = "Test Event",
    slug: str | None = None,
    status: EventStatus = EventStatus.DRAFT,
    custom_fields_schema: list[dict] | None = None,
) -> Event:
    """Создать событие напрямую в БД через доменный сервис."""
    svc = EventService(
        session,
        event_repo=EventRepository(session),
        org_repo=OrganizationRepository(session),
    )
    event = await svc.create(
        org.id,
        CreateEventInput(
            title=title,
            slug=slug,
            schedule={
                "type": "single",
                "starts_at": "2026-12-31T20:00:00+03:00",
                "ends_at": "2027-01-01T03:00:00+03:00",
            },
            capacity_policy={"type": "unlimited"},
            custom_fields_schema=custom_fields_schema,
        ),
    )
    if status != EventStatus.DRAFT:
        event.status = status
        await session.flush()
    return event


async def _add_tariff(
    session: AsyncSession,
    event: Event,
    org: Organization,
    *,
    name: str = "Standard",
    price_kopecks: int = 200000,
    is_active: bool = True,
) -> Tariff:
    """Добавить тариф к событию напрямую в БД."""
    tariff = Tariff(
        id=uuid4(),
        event_id=event.id,
        organization_id=org.id,
        name=name,
        price_kopecks=price_kopecks,
        is_active=is_active,
    )
    session.add(tariff)
    await session.flush()
    return tariff


# ---------------------------------------------------------------------------
# Тесты
# ---------------------------------------------------------------------------


class TestPublicEvents:
    """Тесты публичных эндпоинтов событий."""

    @pytest.fixture(autouse=True)
    async def _setup(self, organizer_user, superadmin_user) -> None:
        """Гарантируем что тестовые пользователи созданы."""
        pass

    async def _get_org(self, session: AsyncSession) -> Organization:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_email("organizer@test-org.example.com")
        org_repo = OrganizationRepository(session)
        return await org_repo.get_by_id(user.organization_id)

    # --- Список событий ---

    async def test_list_returns_only_published(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """GET /public/events возвращает только published события."""
        org = await self._get_org(async_session)

        # Создаём события во всех статусах
        await _create_event_in_org(async_session, org, title="Draft", status=EventStatus.DRAFT)
        await _create_event_in_org(async_session, org, title="Pending", status=EventStatus.PENDING_MODERATION)
        await _create_event_in_org(async_session, org, title="Published", status=EventStatus.PUBLISHED)
        await _create_event_in_org(async_session, org, title="Archived", status=EventStatus.ARCHIVED)

        resp = await client.get(
            "/api/v1/public/events",
            headers={"X-Tenant-Slug": TEST_ORG_SLUG},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["title"] == "Published"

    async def test_list_returns_only_current_org(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """GET /public/events возвращает события только текущей организации."""
        org_a = await self._get_org(async_session)

        # Создаём вторую организацию
        org_b = Organization(
            id=uuid4(), slug="public-org-b", name="Org B", status=OrganizationStatus.ACTIVE
        )
        async_session.add(org_b)
        await async_session.flush()

        # Создаём published события в обеих организациях
        await _create_event_in_org(async_session, org_a, title="Event A", status=EventStatus.PUBLISHED)
        await _create_event_in_org(async_session, org_b, title="Event B", status=EventStatus.PUBLISHED)

        # Запрашиваем от имени org A
        resp = await client.get(
            "/api/v1/public/events",
            headers={"X-Tenant-Slug": TEST_ORG_SLUG},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["title"] == "Event A"

        # Запрашиваем от имени org B
        resp_b = await client.get(
            "/api/v1/public/events",
            headers={"X-Tenant-Slug": "public-org-b"},
        )
        assert resp_b.status_code == 200
        items_b = resp_b.json()["items"]
        assert len(items_b) == 1
        assert items_b[0]["title"] == "Event B"

    async def test_list_draft_not_visible(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """Draft-события не видны в публичном списке."""
        org = await self._get_org(async_session)
        await _create_event_in_org(async_session, org, title="Draft Only", status=EventStatus.DRAFT)

        resp = await client.get(
            "/api/v1/public/events",
            headers={"X-Tenant-Slug": TEST_ORG_SLUG},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 0

    async def test_list_archived_not_visible(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """Archived-события не видны в публичном списке."""
        org = await self._get_org(async_session)
        await _create_event_in_org(async_session, org, title="Archived Only", status=EventStatus.ARCHIVED)

        resp = await client.get(
            "/api/v1/public/events",
            headers={"X-Tenant-Slug": TEST_ORG_SLUG},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 0

    # --- Детали события по slug ---

    async def test_get_by_slug_returns_published(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """GET /public/events/{slug} возвращает published событие."""
        org = await self._get_org(async_session)
        event = await _create_event_in_org(
            async_session, org, title="Pub Event", slug="pub-event", status=EventStatus.PUBLISHED
        )

        resp = await client.get(
            f"/api/v1/public/events/{event.slug}",
            headers={"X-Tenant-Slug": TEST_ORG_SLUG},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "Pub Event"
        assert body["slug"] == event.slug

    async def test_get_by_slug_draft_returns_404(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """GET /public/events/{slug} для draft возвращает 404."""
        org = await self._get_org(async_session)
        event = await _create_event_in_org(
            async_session, org, title="Draft Event", slug="draft-event", status=EventStatus.DRAFT
        )

        resp = await client.get(
            f"/api/v1/public/events/{event.slug}",
            headers={"X-Tenant-Slug": TEST_ORG_SLUG},
        )
        assert resp.status_code == 404

    async def test_get_by_slug_archived_returns_404(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """GET /public/events/{slug} для archived возвращает 404."""
        org = await self._get_org(async_session)
        event = await _create_event_in_org(
            async_session, org, title="Archived Event", slug="archived-event", status=EventStatus.ARCHIVED
        )

        resp = await client.get(
            f"/api/v1/public/events/{event.slug}",
            headers={"X-Tenant-Slug": TEST_ORG_SLUG},
        )
        assert resp.status_code == 404

    async def test_get_by_slug_other_org_returns_404(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """GET /public/events/{slug} для события другой организации возвращает 404."""

        # Создаём другую организацию
        other_org = Organization(
            id=uuid4(), slug="public-other", name="Other", status=OrganizationStatus.ACTIVE
        )
        async_session.add(other_org)
        await async_session.flush()

        # Создаём published событие в другой организации
        event = await _create_event_in_org(
            async_session, other_org, title="Other Event", slug="other-event", status=EventStatus.PUBLISHED
        )

        # Запрашиваем от имени test-org — slug принадлежит другой org, 404
        resp = await client.get(
            f"/api/v1/public/events/{event.slug}",
            headers={"X-Tenant-Slug": TEST_ORG_SLUG},
        )
        assert resp.status_code == 404

    # --- Детали: тарифы и custom fields ---

    async def test_event_details_include_tariffs(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """Детали события включают список активных тарифов."""
        org = await self._get_org(async_session)
        event = await _create_event_in_org(
            async_session, org, title="With Tariffs", slug="with-tariffs", status=EventStatus.PUBLISHED
        )
        await _add_tariff(async_session, event, org, name="VIP", price_kopecks=500000)

        resp = await client.get(
            f"/api/v1/public/events/{event.slug}",
            headers={"X-Tenant-Slug": TEST_ORG_SLUG},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "tariffs" in body
        assert len(body["tariffs"]) == 1
        assert body["tariffs"][0]["name"] == "VIP"
        assert body["tariffs"][0]["price_kopecks"] == 500000

    async def test_event_details_include_custom_fields_schema(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """Детали события включают custom_fields_schema."""
        org = await self._get_org(async_session)
        schema = [{"id": "comment", "label": "Комментарий", "type": "text", "required": False}]
        event = await _create_event_in_org(
            async_session, org,
            title="With Fields",
            slug="with-fields",
            status=EventStatus.PUBLISHED,
            custom_fields_schema=schema,
        )

        resp = await client.get(
            f"/api/v1/public/events/{event.slug}",
            headers={"X-Tenant-Slug": TEST_ORG_SLUG},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["custom_fields_schema"] is not None
        assert len(body["custom_fields_schema"]) == 1
        assert body["custom_fields_schema"][0]["id"] == "comment"

    async def test_event_details_only_active_tariffs(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """В деталях события только тарифы с is_active=true."""
        org = await self._get_org(async_session)
        event = await _create_event_in_org(
            async_session, org, title="Mixed Tariffs", slug="mixed-tariffs", status=EventStatus.PUBLISHED
        )
        await _add_tariff(async_session, event, org, name="Active", price_kopecks=100000, is_active=True)
        await _add_tariff(async_session, event, org, name="Inactive", price_kopecks=200000, is_active=False)

        resp = await client.get(
            f"/api/v1/public/events/{event.slug}",
            headers={"X-Tenant-Slug": TEST_ORG_SLUG},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "tariffs" in body
        assert len(body["tariffs"]) == 1
        assert body["tariffs"][0]["name"] == "Active"