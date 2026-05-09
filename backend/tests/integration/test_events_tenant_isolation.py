"""Integration-тесты tenant isolation для событий.

Проверяет что организатор A не видит/не может менять события организатора B.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from paytools.db.models.enums import EventStatus
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


async def _register_and_approve_org(
    client: AsyncClient, suffix: str
) -> tuple[str, str, str]:
    """Регистрирует и одобряет организацию, возвращает (org_id, token, slug)."""
    slug = f"iso-{suffix}"
    reg_resp = await client.post(
        "/api/v1/public/organizations/register",
        json={
            "email": f"iso-{suffix}@example.com",
            "password": "StrongPass123!",
            "first_name": "Iso",
            "last_name": suffix.capitalize(),
            "organization_name": f"Isolation {suffix}",
            "organization_slug": slug,
            "accept_terms": True,
        },
    )
    assert reg_resp.status_code == 201
    org_id = reg_resp.json()["organization_id"]

    sa_token = await _get_superadmin_token(client)
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
    return org_id, org_login.json()["access_token"], slug


async def _get_token(client: AsyncClient, email: str, password: str) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
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


# ---------------------------------------------------------------------------
# Тесты
# ---------------------------------------------------------------------------


class TestEventsTenantIsolation:
    """Тесты изоляции данных событий между организациями."""

    @pytest.fixture(autouse=True)
    async def _setup(self, organizer_user, superadmin_user) -> None:
        """Гарантируем что тестовые пользователи созданы."""
        pass

    # --- Organizer A vs Organizer B: список ---

    async def test_organizer_a_cannot_see_event_of_b(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """Organizer A не видит события организации B в своём списке."""
        org_a = await _get_test_org(async_session)
        _, token_b, slug_b = await _register_and_approve_org(client, "see")

        # Создаём события
        await _create_event(async_session, org_a, title="Event A")
        org_repo = OrganizationRepository(async_session)
        org_b = await org_repo.get_by_slug(slug_b)
        await _create_event(async_session, org_b, title="Event B")

        # Организатор A видит только свои события
        token_a = await _get_token(
            client, "organizer@test-org.example.com", "Organizer123!"
        )
        resp_a = await client.get(
            "/api/v1/organizer/events",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert resp_a.status_code == 200
        titles_a = {item["title"] for item in resp_a.json()["items"]}
        assert "Event A" in titles_a
        assert "Event B" not in titles_a

        # Организатор B видит только свои
        resp_b = await client.get(
            "/api/v1/organizer/events",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert resp_b.status_code == 200
        titles_b = {item["title"] for item in resp_b.json()["items"]}
        assert "Event B" in titles_b
        assert "Event A" not in titles_b

    # --- Organizer A vs Organizer B: GET по ID ---

    async def test_organizer_a_get_event_b_returns_404(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """GET события организации B от организатора A → 403/404."""
        _, _token_b, slug_b = await _register_and_approve_org(client, "get")

        org_repo = OrganizationRepository(async_session)
        org_b = await org_repo.get_by_slug(slug_b)
        event_b_id = await _create_event(async_session, org_b, title="B's Event")

        token_a = await _get_token(
            client, "organizer@test-org.example.com", "Organizer123!"
        )
        resp = await client.get(
            f"/api/v1/organizer/events/{event_b_id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        # Tenant isolation: не должен видеть чужое событие
        assert resp.status_code in (403, 404)

    # --- Organizer A vs Organizer B: PATCH ---

    async def test_organizer_a_cannot_patch_event_b(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """PATCH события организации B от организатора A → 404."""
        _, _token_b, slug_b = await _register_and_approve_org(client, "patch")

        org_repo = OrganizationRepository(async_session)
        org_b = await org_repo.get_by_slug(slug_b)
        event_b_id = await _create_event(async_session, org_b, title="B's Event")

        token_a = await _get_token(
            client, "organizer@test-org.example.com", "Organizer123!"
        )
        resp = await client.patch(
            f"/api/v1/organizer/events/{event_b_id}",
            json={"title": "Hacked Title"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        # Tenant isolation: организатор A не может менять события org B
        assert resp.status_code == 404

    # --- Organizer A vs Organizer B: DELETE ---

    async def test_organizer_a_cannot_delete_event_b(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """DELETE события организации B от организатора A → 404."""
        _, _token_b, slug_b = await _register_and_approve_org(client, "del")

        org_repo = OrganizationRepository(async_session)
        org_b = await org_repo.get_by_slug(slug_b)
        event_b_id = await _create_event(async_session, org_b, title="B's Event")

        token_a = await _get_token(
            client, "organizer@test-org.example.com", "Organizer123!"
        )
        resp = await client.delete(
            f"/api/v1/organizer/events/{event_b_id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        # Tenant isolation: организатор A не может удалять события org B
        assert resp.status_code == 404

    # --- Organizer A vs Organizer B: tariff ---

    async def test_organizer_a_cannot_add_tariff_to_event_b(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """POST тарифа к событию организации B от организатора A → 404."""
        _, _token_b, slug_b = await _register_and_approve_org(client, "tariff")

        org_repo = OrganizationRepository(async_session)
        org_b = await org_repo.get_by_slug(slug_b)
        event_b_id = await _create_event(async_session, org_b, title="B's Event")

        token_a = await _get_token(
            client, "organizer@test-org.example.com", "Organizer123!"
        )
        resp = await client.post(
            f"/api/v1/organizer/events/{event_b_id}/tariffs",
            json={"name": "Hacked Tariff", "price_kopecks": 100},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        # Tenant isolation: организатор A не может добавлять тарифы в события org B
        assert resp.status_code == 404

    # --- Public tenant isolation ---

    async def test_public_subdomain_a_does_not_show_b_events(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """X-Tenant-Slug: a не показывает published события организации B."""
        org_a = await _get_test_org(async_session)
        _, _token_b, slug_b = await _register_and_approve_org(client, "public")

        org_repo = OrganizationRepository(async_session)
        org_b = await org_repo.get_by_slug(slug_b)

        # Создаём published события в обеих организациях
        await _create_event(async_session, org_a, title="Event A", status=EventStatus.PUBLISHED)
        await _create_event(async_session, org_b, title="Event B", status=EventStatus.PUBLISHED)

        # Запрашиваем с X-Tenant-Slug = test-org → только A
        resp_a = await client.get(
            "/api/v1/public/events",
            headers={"X-Tenant-Slug": "test-org"},
        )
        assert resp_a.status_code == 200
        titles_a = {item["title"] for item in resp_a.json()["items"]}
        assert "Event A" in titles_a
        assert "Event B" not in titles_a

        # Запрашиваем с X-Tenant-Slug = slug_b → только B
        resp_b = await client.get(
            "/api/v1/public/events",
            headers={"X-Tenant-Slug": slug_b},
        )
        assert resp_b.status_code == 200
        titles_b = {item["title"] for item in resp_b.json()["items"]}
        assert "Event B" in titles_b
        assert "Event A" not in titles_b

    async def test_access_token_org_from_jwt_not_subdomain(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """Организатор A видит свои события — org_id из JWT.

        Middleware приоритезирует JWT над subdomain. Организатор A
        всегда видит события своей организации через organizer-эндпоинты.
        """
        org_a = await _get_test_org(async_session)
        _, _token_b, slug_b = await _register_and_approve_org(client, "jwt")

        org_repo = OrganizationRepository(async_session)
        org_b = await org_repo.get_by_slug(slug_b)

        # Создаём события в обеих организациях
        await _create_event(async_session, org_a, title="Event A")
        await _create_event(async_session, org_b, title="Event B")

        # Организатор A делает запрос — видит только свои события
        token_a = await _get_token(
            client, "organizer@test-org.example.com", "Organizer123!"
        )
        resp = await client.get(
            "/api/v1/organizer/events",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert resp.status_code == 200
        titles = {item["title"] for item in resp.json()["items"]}
        assert "Event A" in titles
        assert "Event B" not in titles

    # --- Extended: submit, publish, image upload, tariff update/delete ---

    async def test_organizer_a_cannot_submit_event_b(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """POST /organizer/events/{id}/submit на событие org B → 404."""
        _, _token_b, slug_b = await _register_and_approve_org(client, "submit")

        org_repo = OrganizationRepository(async_session)
        org_b = await org_repo.get_by_slug(slug_b)
        event_b_id = await _create_event(async_session, org_b, title="B's Event")

        token_a = await _get_token(
            client, "organizer@test-org.example.com", "Organizer123!"
        )
        resp = await client.post(
            f"/api/v1/organizer/events/{event_b_id}/submit",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert resp.status_code == 404

    async def test_organizer_a_cannot_publish_event_b(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """POST /organizer/events/{id}/publish на событие org B → 404."""
        _, _token_b, slug_b = await _register_and_approve_org(client, "pub")

        org_repo = OrganizationRepository(async_session)
        org_b = await org_repo.get_by_slug(slug_b)
        event_b_id = await _create_event(
            async_session, org_b, title="B's Event",
            status=EventStatus.PENDING_MODERATION,
        )

        token_a = await _get_token(
            client, "organizer@test-org.example.com", "Organizer123!"
        )
        resp = await client.post(
            f"/api/v1/organizer/events/{event_b_id}/publish",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert resp.status_code == 404

    async def test_organizer_a_cannot_upload_image_to_event_b(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """POST /organizer/events/{id}/images на событие org B → 404."""
        _, _token_b, slug_b = await _register_and_approve_org(client, "img")

        org_repo = OrganizationRepository(async_session)
        org_b = await org_repo.get_by_slug(slug_b)
        event_b_id = await _create_event(async_session, org_b, title="B's Event")

        token_a = await _get_token(
            client, "organizer@test-org.example.com", "Organizer123!"
        )
        # Отправляем фейковый JPEG
        resp = await client.post(
            f"/api/v1/organizer/events/{event_b_id}/images",
            headers={"Authorization": f"Bearer {token_a}"},
            data={"kind": "card"},
            files={"file": ("test.jpg", b"fake-jpeg-data", "image/jpeg")},
        )
        assert resp.status_code == 404

    async def test_organizer_a_cannot_update_tariff_of_b(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """PATCH /organizer/tariffs/{id} на тариф org B → 404."""
        _, _token_b, slug_b = await _register_and_approve_org(client, "tupd")

        org_repo = OrganizationRepository(async_session)
        org_b = await org_repo.get_by_slug(slug_b)
        event_b_id = await _create_event(async_session, org_b, title="B's Event")

        # Создаём тариф через организатора B
        token_b = await _get_token(
            client, f"iso-tupd@example.com", "StrongPass123!"
        )
        tariff_resp = await client.post(
            f"/api/v1/organizer/events/{event_b_id}/tariffs",
            json={"name": "B Tariff", "price_kopecks": 1000},
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert tariff_resp.status_code == 201
        tariff_id = tariff_resp.json()["id"]

        # Организатор A пытается обновить
        token_a = await _get_token(
            client, "organizer@test-org.example.com", "Organizer123!"
        )
        resp = await client.patch(
            f"/api/v1/organizer/tariffs/{tariff_id}",
            json={"name": "Hacked"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert resp.status_code == 404

    async def test_organizer_a_cannot_delete_tariff_of_b(
        self, client: AsyncClient, async_session: AsyncSession
    ) -> None:
        """DELETE /organizer/tariffs/{id} на тариф org B → 404."""
        _, _token_b, slug_b = await _register_and_approve_org(client, "tdel")

        org_repo = OrganizationRepository(async_session)
        org_b = await org_repo.get_by_slug(slug_b)
        event_b_id = await _create_event(async_session, org_b, title="B's Event")

        # Создаём тариф через организатора B
        token_b = await _get_token(
            client, f"iso-tdel@example.com", "StrongPass123!"
        )
        tariff_resp = await client.post(
            f"/api/v1/organizer/events/{event_b_id}/tariffs",
            json={"name": "Del Tariff", "price_kopecks": 500},
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert tariff_resp.status_code == 201
        tariff_id = tariff_resp.json()["id"]

        # Организатор A пытается удалить
        token_a = await _get_token(
            client, "organizer@test-org.example.com", "Organizer123!"
        )
        resp = await client.delete(
            f"/api/v1/organizer/tariffs/{tariff_id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert resp.status_code == 404