"""Unit-тесты EventService: создание, обновление, статусные переходы.

Использует реальную БД через async_session (транзакционный rollback).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from paytools.core.errors import ForbiddenError
from paytools.db.models.enums import EventStatus, OrganizationStatus, UserRole
from paytools.db.models.event import Event
from paytools.db.models.organization import Organization
from paytools.db.models.user import User
from paytools.db.repositories.event import EventRepository
from paytools.db.repositories.organization import OrganizationRepository
from paytools.domain.events.errors import (
    CannotPublishError,
    EventNotEditableError,
    EventNotFoundError,
    InvalidStatusTransitionError,
    PublishedFieldsRestrictedError,
)
from paytools.domain.events.service import (
    CreateEventInput,
    EventService,
    UpdateEventInput,
)


# ---------------------------------------------------------------------------
# Хелперы
# ---------------------------------------------------------------------------


def _valid_create_data(**overrides: object) -> CreateEventInput:
    kwargs: dict = {
        "title": "Test Event",
        "slug": None,
        "description_md": "Test description",
        "location_name": "Test Location",
        "location_address": "Test Address",
        "schedule": {
            "type": "single",
            "starts_at": "2026-12-31T20:00:00+03:00",
            "ends_at": "2027-01-01T03:00:00+03:00",
        },
        "capacity_policy": {"type": "unlimited"},
    }
    kwargs.update(overrides)
    return CreateEventInput(**kwargs)


def _make_org(
    auto_publish: bool = False,
    status: OrganizationStatus = OrganizationStatus.ACTIVE,
) -> Organization:
    return Organization(
        id=uuid4(),
        slug=f"test-org-{uuid4().hex[:8]}",
        name="Test Org",
        status=status,
        auto_publish_enabled=auto_publish,
    )


def _make_user(
    role: UserRole = UserRole.ORGANIZER,
    org_id: uuid4 | None = None,
) -> User:
    return User(
        id=uuid4(),
        email=f"test-{uuid4().hex[:8]}@example.com",
        password_hash="hashed",
        first_name="Test",
        last_name="User",
        role=role,
        is_active=True,
        organization_id=org_id,
    )


# ---------------------------------------------------------------------------
# Тесты: EventService.create
# ---------------------------------------------------------------------------


class TestEventServiceCreate:
    """Тесты создания события."""

    async def test_create_returns_draft_event(
        self, async_session: AsyncSession
    ) -> None:
        """Созданное событие имеет статус draft."""
        org = _make_org()
        async_session.add(org)
        await async_session.flush()

        svc = EventService(
            async_session,
            event_repo=EventRepository(async_session),
            org_repo=OrganizationRepository(async_session),
        )
        event = await svc.create(org.id, _valid_create_data())

        assert event.status == EventStatus.DRAFT
        assert event.title == "Test Event"
        assert event.organization_id == org.id

    async def test_create_sets_correct_fields(
        self, async_session: AsyncSession
    ) -> None:
        """Все переданные поля сохраняются корректно."""
        org = _make_org()
        async_session.add(org)
        await async_session.flush()

        svc = EventService(
            async_session,
            event_repo=EventRepository(async_session),
            org_repo=OrganizationRepository(async_session),
        )
        event = await svc.create(
            org.id,
            _valid_create_data(
                title="Новый год 2026",
                description_md="Празднуем!",
                location_name="Ресторан Чайка",
                location_address="ул. Пушкина, 10",
            ),
        )

        assert event.title == "Новый год 2026"
        assert event.description_md == "Празднуем!"
        assert event.location_name == "Ресторан Чайка"
        assert event.location_address == "ул. Пушкина, 10"
        assert event.schedule["type"] == "single"
        assert event.capacity_policy["type"] == "unlimited"

    async def test_slug_auto_generated_from_title(
        self, async_session: AsyncSession
    ) -> None:
        """Если slug не передан — генерируется из title."""
        org = _make_org()
        async_session.add(org)
        await async_session.flush()

        svc = EventService(
            async_session,
            event_repo=EventRepository(async_session),
            org_repo=OrganizationRepository(async_session),
        )
        event = await svc.create(
            org.id, _valid_create_data(title="Новый год 2026", slug=None)
        )

        assert event.slug is not None
        assert len(event.slug) > 0
        # Slug сгенерирован из title (может быть разным в зависимости от транслитерации)

    async def test_slug_unique_within_org(
        self, async_session: AsyncSession
    ) -> None:
        """Slug должен быть уникален в рамках одной организации."""
        org = _make_org()
        async_session.add(org)
        await async_session.flush()

        svc = EventService(
            async_session,
            event_repo=EventRepository(async_session),
            org_repo=OrganizationRepository(async_session),
        )

        # Первое событие с явным slug
        event1 = await svc.create(
            org.id, _valid_create_data(title="Event One", slug="my-event")
        )
        assert event1.slug == "my-event"

        # Второе событие с тем же slug — должен добавиться суффикс
        event2 = await svc.create(
            org.id, _valid_create_data(title="Event Two", slug="my-event")
        )
        assert event2.slug != "my-event"
        assert event2.slug.startswith("my-event")

    async def test_slug_can_be_same_in_different_orgs(
        self, async_session: AsyncSession
    ) -> None:
        """Одинаковый slug разрешён в разных организациях."""
        org1 = _make_org()
        org2 = _make_org()
        async_session.add_all([org1, org2])
        await async_session.flush()

        svc = EventService(
            async_session,
            event_repo=EventRepository(async_session),
            org_repo=OrganizationRepository(async_session),
        )

        event1 = await svc.create(
            org1.id, _valid_create_data(title="Event", slug="same-slug")
        )
        event2 = await svc.create(
            org2.id, _valid_create_data(title="Event", slug="same-slug")
        )

        assert event1.slug == "same-slug"
        assert event2.slug == "same-slug"
        assert event1.organization_id != event2.organization_id

    async def test_create_with_custom_fields(
        self, async_session: AsyncSession
    ) -> None:
        """Создание события с custom_fields_schema."""
        org = _make_org()
        async_session.add(org)
        await async_session.flush()

        svc = EventService(
            async_session,
            event_repo=EventRepository(async_session),
            org_repo=OrganizationRepository(async_session),
        )
        event = await svc.create(
            org.id,
            _valid_create_data(
                custom_fields_schema=[
                    {"id": "comment", "label": "Комментарий", "type": "text", "required": False}
                ]
            ),
        )

        assert event.custom_fields_schema is not None
        assert len(event.custom_fields_schema) == 1
        assert event.custom_fields_schema[0]["id"] == "comment"


# ---------------------------------------------------------------------------
# Тесты: EventService.update
# ---------------------------------------------------------------------------


class TestEventServiceUpdate:
    """Тесты обновления события в разных статусах."""

    async def _create_event(
        self, session: AsyncSession, org: Organization, status: EventStatus = EventStatus.DRAFT
    ) -> Event:
        svc = EventService(
            session,
            event_repo=EventRepository(session),
            org_repo=OrganizationRepository(session),
        )
        event = await svc.create(org.id, _valid_create_data())
        if status != EventStatus.DRAFT:
            event.status = status
            await session.flush()
        return event

    async def test_update_in_draft_allowed_all_fields(
        self, async_session: AsyncSession
    ) -> None:
        """В статусе draft разрешено обновлять все поля."""
        org = _make_org()
        async_session.add(org)
        await async_session.flush()

        event = await self._create_event(async_session, org)
        user = _make_user(org_id=org.id)

        svc = EventService(
            async_session,
            event_repo=EventRepository(async_session),
            org_repo=OrganizationRepository(async_session),
        )
        updated = await svc.update(
            event.id,
            UpdateEventInput(
                title="Updated Title",
                description_md="Updated description",
                schedule={"type": "period", "starts_at": "2026-07-01T00:00:00+03:00", "ends_at": "2026-07-05T23:59:59+03:00"},
            ),
            by_user=user,
        )

        assert updated.title == "Updated Title"
        assert updated.description_md == "Updated description"
        assert updated.schedule["type"] == "period"

    async def test_update_in_published_forbidden_schedule_changes(
        self, async_session: AsyncSession
    ) -> None:
        """В статусе published запрещено менять schedule."""
        org = _make_org()
        async_session.add(org)
        await async_session.flush()

        event = await self._create_event(async_session, org, EventStatus.PUBLISHED)
        user = _make_user(org_id=org.id)

        svc = EventService(
            async_session,
            event_repo=EventRepository(async_session),
            org_repo=OrganizationRepository(async_session),
        )
        with pytest.raises(PublishedFieldsRestrictedError):
            await svc.update(
                event.id,
                UpdateEventInput(
                    schedule={"type": "period", "starts_at": "2026-07-01T00:00:00+03:00", "ends_at": "2026-07-05T23:59:59+03:00"},
                ),
                by_user=user,
            )

    async def test_update_in_published_forbidden_capacity_changes(
        self, async_session: AsyncSession
    ) -> None:
        """В статусе published запрещено менять capacity_policy."""
        org = _make_org()
        async_session.add(org)
        await async_session.flush()

        event = await self._create_event(async_session, org, EventStatus.PUBLISHED)
        user = _make_user(org_id=org.id)

        svc = EventService(
            async_session,
            event_repo=EventRepository(async_session),
            org_repo=OrganizationRepository(async_session),
        )
        with pytest.raises(PublishedFieldsRestrictedError):
            await svc.update(
                event.id,
                UpdateEventInput(capacity_policy={"type": "total", "limit": 100}),
                by_user=user,
            )

    async def test_update_in_published_allowed_description(
        self, async_session: AsyncSession
    ) -> None:
        """В статусе published разрешено менять description."""
        org = _make_org()
        async_session.add(org)
        await async_session.flush()

        event = await self._create_event(async_session, org, EventStatus.PUBLISHED)
        user = _make_user(org_id=org.id)

        svc = EventService(
            async_session,
            event_repo=EventRepository(async_session),
            org_repo=OrganizationRepository(async_session),
        )
        updated = await svc.update(
            event.id,
            UpdateEventInput(description_md="New description"),
            by_user=user,
        )
        assert updated.description_md == "New description"

    async def test_update_in_published_allowed_location(
        self, async_session: AsyncSession
    ) -> None:
        """В статусе published разрешено менять location."""
        org = _make_org()
        async_session.add(org)
        await async_session.flush()

        event = await self._create_event(async_session, org, EventStatus.PUBLISHED)
        user = _make_user(org_id=org.id)

        svc = EventService(
            async_session,
            event_repo=EventRepository(async_session),
            org_repo=OrganizationRepository(async_session),
        )
        updated = await svc.update(
            event.id,
            UpdateEventInput(location_name="New Location"),
            by_user=user,
        )
        assert updated.location_name == "New Location"

    async def test_update_in_archived_forbidden(
        self, async_session: AsyncSession
    ) -> None:
        """В статусе archived обновление запрещено полностью."""
        org = _make_org()
        async_session.add(org)
        await async_session.flush()

        event = await self._create_event(async_session, org, EventStatus.ARCHIVED)
        user = _make_user(org_id=org.id)

        svc = EventService(
            async_session,
            event_repo=EventRepository(async_session),
            org_repo=OrganizationRepository(async_session),
        )
        with pytest.raises(EventNotEditableError):
            await svc.update(
                event.id,
                UpdateEventInput(title="New Title"),
                by_user=user,
            )


# ---------------------------------------------------------------------------
# Тесты: статусные переходы
# ---------------------------------------------------------------------------


class TestEventServiceSubmitForModeration:
    """Тесты submit_for_moderation."""

    async def _create_event(
        self, session: AsyncSession, org: Organization, status: EventStatus = EventStatus.DRAFT
    ) -> Event:
        svc = EventService(
            session,
            event_repo=EventRepository(session),
            org_repo=OrganizationRepository(session),
        )
        event = await svc.create(org.id, _valid_create_data())
        if status != EventStatus.DRAFT:
            event.status = status
            await session.flush()
        return event

    async def test_submit_from_draft_succeeds(
        self, async_session: AsyncSession
    ) -> None:
        """Из draft можно отправить на модерацию."""
        org = _make_org()
        async_session.add(org)
        await async_session.flush()

        event = await self._create_event(async_session, org)
        svc = EventService(
            async_session,
            event_repo=EventRepository(async_session),
            org_repo=OrganizationRepository(async_session),
        )
        result = await svc.submit_for_moderation(event.id)
        assert result.status == EventStatus.PENDING_MODERATION

    async def test_submit_from_published_raises(
        self, async_session: AsyncSession
    ) -> None:
        """Из published нельзя отправить на модерацию."""
        org = _make_org()
        async_session.add(org)
        await async_session.flush()

        event = await self._create_event(async_session, org, EventStatus.PUBLISHED)
        svc = EventService(
            async_session,
            event_repo=EventRepository(async_session),
            org_repo=OrganizationRepository(async_session),
        )
        with pytest.raises(InvalidStatusTransitionError):
            await svc.submit_for_moderation(event.id)

    async def test_submit_from_archived_raises(
        self, async_session: AsyncSession
    ) -> None:
        """Из archived нельзя отправить на модерацию."""
        org = _make_org()
        async_session.add(org)
        await async_session.flush()

        event = await self._create_event(async_session, org, EventStatus.ARCHIVED)
        svc = EventService(
            async_session,
            event_repo=EventRepository(async_session),
            org_repo=OrganizationRepository(async_session),
        )
        with pytest.raises(InvalidStatusTransitionError):
            await svc.submit_for_moderation(event.id)


class TestEventServicePublish:
    """Тесты publish."""

    async def _create_event(
        self, session: AsyncSession, org: Organization, status: EventStatus = EventStatus.PENDING_MODERATION
    ) -> Event:
        svc = EventService(
            session,
            event_repo=EventRepository(session),
            org_repo=OrganizationRepository(session),
        )
        event = await svc.create(org.id, _valid_create_data())
        event.status = status
        await session.flush()
        return event

    async def test_publish_from_pending_moderation_succeeds(
        self, async_session: AsyncSession
    ) -> None:
        """Из pending_moderation можно опубликовать."""
        org = _make_org(auto_publish=True)
        async_session.add(org)
        await async_session.flush()

        event = await self._create_event(async_session, org)
        user = _make_user(org_id=org.id)
        svc = EventService(
            async_session,
            event_repo=EventRepository(async_session),
            org_repo=OrganizationRepository(async_session),
        )
        result = await svc.publish(event.id, by_user=user)
        assert result.status == EventStatus.PUBLISHED
        assert result.published_at is not None

    async def test_publish_by_superadmin_always_allowed(
        self, async_session: AsyncSession
    ) -> None:
        """Superadmin может опубликовать событие любой организации."""
        org = _make_org(auto_publish=False)
        async_session.add(org)
        await async_session.flush()

        event = await self._create_event(async_session, org)
        superadmin = _make_user(role=UserRole.SUPERADMIN)
        svc = EventService(
            async_session,
            event_repo=EventRepository(async_session),
            org_repo=OrganizationRepository(async_session),
        )
        result = await svc.publish(event.id, by_user=superadmin)
        assert result.status == EventStatus.PUBLISHED

    async def test_publish_by_organizer_without_auto_publish_raises(
        self, async_session: AsyncSession
    ) -> None:
        """Organizer НЕ может опубликовать если auto_publish_enabled=false."""
        org = _make_org(auto_publish=False)
        async_session.add(org)
        await async_session.flush()

        event = await self._create_event(async_session, org)
        user = _make_user(org_id=org.id)
        svc = EventService(
            async_session,
            event_repo=EventRepository(async_session),
            org_repo=OrganizationRepository(async_session),
        )
        with pytest.raises(CannotPublishError):
            await svc.publish(event.id, by_user=user)

    async def test_publish_from_draft_raises(
        self, async_session: AsyncSession
    ) -> None:
        """Из draft нельзя опубликовать (нужно сначала submit)."""
        org = _make_org(auto_publish=True)
        async_session.add(org)
        await async_session.flush()

        event = await self._create_event(async_session, org, EventStatus.DRAFT)
        user = _make_user(org_id=org.id)
        svc = EventService(
            async_session,
            event_repo=EventRepository(async_session),
            org_repo=OrganizationRepository(async_session),
        )
        with pytest.raises(InvalidStatusTransitionError):
            await svc.publish(event.id, by_user=user)


class TestEventServiceReject:
    """Тесты reject."""

    async def _create_event(
        self, session: AsyncSession, org: Organization
    ) -> Event:
        svc = EventService(
            session,
            event_repo=EventRepository(session),
            org_repo=OrganizationRepository(session),
        )
        event = await svc.create(org.id, _valid_create_data())
        event.status = EventStatus.PENDING_MODERATION
        await session.flush()
        return event

    async def test_reject_from_pending_moderation_succeeds(
        self, async_session: AsyncSession
    ) -> None:
        """Из pending_moderation можно отклонить."""
        org = _make_org()
        async_session.add(org)
        await async_session.flush()

        event = await self._create_event(async_session, org)
        superadmin = _make_user(role=UserRole.SUPERADMIN)
        svc = EventService(
            async_session,
            event_repo=EventRepository(async_session),
            org_repo=OrganizationRepository(async_session),
        )
        result = await svc.reject(event.id, note="Не соответствует требованиям", by_user=superadmin)
        assert result.status == EventStatus.REJECTED
        assert result.moderation_note == "Не соответствует требованиям"

    async def test_reject_by_organizer_raises(
        self, async_session: AsyncSession
    ) -> None:
        """Organizer не может отклонить событие."""
        org = _make_org()
        async_session.add(org)
        await async_session.flush()

        event = await self._create_event(async_session, org)
        user = _make_user(org_id=org.id)
        svc = EventService(
            async_session,
            event_repo=EventRepository(async_session),
            org_repo=OrganizationRepository(async_session),
        )
        with pytest.raises(CannotPublishError):
            await svc.reject(event.id, note="test", by_user=user)


class TestEventServiceArchive:
    """Тесты archive (soft-delete)."""

    async def _create_event(
        self, session: AsyncSession, org: Organization, status: EventStatus = EventStatus.DRAFT
    ) -> Event:
        svc = EventService(
            session,
            event_repo=EventRepository(session),
            org_repo=OrganizationRepository(session),
        )
        event = await svc.create(org.id, _valid_create_data())
        if status != EventStatus.DRAFT:
            event.status = status
            await session.flush()
        return event

    async def test_archive_sets_status_to_archived(
        self, async_session: AsyncSession
    ) -> None:
        """Архивация переводит событие в статус archived."""
        org = _make_org()
        async_session.add(org)
        await async_session.flush()

        event = await self._create_event(async_session, org)
        svc = EventService(
            async_session,
            event_repo=EventRepository(async_session),
            org_repo=OrganizationRepository(async_session),
        )
        await svc.archive(event.id)

        # Перезагружаем из БД
        repo = EventRepository(async_session)
        archived = await repo.get(event.id)
        assert archived is not None
        assert archived.status == EventStatus.ARCHIVED

    async def test_archive_is_idempotent(
        self, async_session: AsyncSession
    ) -> None:
        """Повторная архивация идемпотентна."""
        org = _make_org()
        async_session.add(org)
        await async_session.flush()

        event = await self._create_event(async_session, org, EventStatus.ARCHIVED)
        svc = EventService(
            async_session,
            event_repo=EventRepository(async_session),
            org_repo=OrganizationRepository(async_session),
        )
        # Не должно быть исключения
        await svc.archive(event.id)

    async def test_archive_from_published_succeeds(
        self, async_session: AsyncSession
    ) -> None:
        """Архивировать можно из published."""
        org = _make_org()
        async_session.add(org)
        await async_session.flush()

        event = await self._create_event(async_session, org, EventStatus.PUBLISHED)
        svc = EventService(
            async_session,
            event_repo=EventRepository(async_session),
            org_repo=OrganizationRepository(async_session),
        )
        await svc.archive(event.id)

        repo = EventRepository(async_session)
        archived = await repo.get(event.id)
        assert archived.status == EventStatus.ARCHIVED


# ---------------------------------------------------------------------------
# Тесты: EventService.list_public
# ---------------------------------------------------------------------------


class TestEventServiceListPublic:
    """Тесты публичного списка событий."""

    async def test_returns_only_published(
        self, async_session: AsyncSession
    ) -> None:
        """list_public возвращает только published события."""
        org = _make_org()
        async_session.add(org)
        await async_session.flush()

        svc = EventService(
            async_session,
            event_repo=EventRepository(async_session),
            org_repo=OrganizationRepository(async_session),
        )

        # Создаём draft и published события
        draft = await svc.create(org.id, _valid_create_data(title="Draft Event"))
        pub = await svc.create(org.id, _valid_create_data(title="Published Event"))
        pub.status = EventStatus.PUBLISHED
        await async_session.flush()

        events, total = await svc.list_public(org.id)
        assert total == 1
        assert events[0].id == pub.id

    async def test_returns_only_current_org(
        self, async_session: AsyncSession
    ) -> None:
        """list_public фильтрует по organization_id."""
        org1 = _make_org()
        org2 = _make_org()
        async_session.add_all([org1, org2])
        await async_session.flush()

        svc = EventService(
            async_session,
            event_repo=EventRepository(async_session),
            org_repo=OrganizationRepository(async_session),
        )

        event1 = await svc.create(org1.id, _valid_create_data(title="Org1 Event"))
        event1.status = EventStatus.PUBLISHED
        event2 = await svc.create(org2.id, _valid_create_data(title="Org2 Event"))
        event2.status = EventStatus.PUBLISHED
        await async_session.flush()

        events, total = await svc.list_public(org1.id)
        assert total == 1
        assert events[0].id == event1.id

    async def test_draft_not_visible(
        self, async_session: AsyncSession
    ) -> None:
        """Draft-события не видны в публичном списке."""
        org = _make_org()
        async_session.add(org)
        await async_session.flush()

        svc = EventService(
            async_session,
            event_repo=EventRepository(async_session),
            org_repo=OrganizationRepository(async_session),
        )
        await svc.create(org.id, _valid_create_data(title="Draft Event"))

        events, total = await svc.list_public(org.id)
        assert total == 0

    async def test_archived_not_visible(
        self, async_session: AsyncSession
    ) -> None:
        """Archived-события не видны в публичном списке."""
        org = _make_org()
        async_session.add(org)
        await async_session.flush()

        svc = EventService(
            async_session,
            event_repo=EventRepository(async_session),
            org_repo=OrganizationRepository(async_session),
        )
        event = await svc.create(org.id, _valid_create_data(title="Archived Event"))
        event.status = EventStatus.ARCHIVED
        await async_session.flush()

        events, total = await svc.list_public(org.id)
        assert total == 0