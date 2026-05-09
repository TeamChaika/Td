"""Unit-тесты TariffService: создание, обновление, удаление тарифов.

Использует реальную БД через async_session (транзакционный rollback).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from paytools.db.models.enums import EventStatus, OrganizationStatus
from paytools.db.models.event import Event, Tariff
from paytools.db.models.organization import Organization
from paytools.db.repositories.event import EventRepository
from paytools.db.repositories.tariff import TariffRepository
from paytools.domain.tariffs.errors import (
    EventNotEditableForTariffError,
    TariffNotFoundError,
    TariffPriceLockedError,
)
from paytools.domain.tariffs.service import (
    CreateTariffInput,
    TariffService,
    UpdateTariffInput,
)


# ---------------------------------------------------------------------------
# Хелперы
# ---------------------------------------------------------------------------


def _make_org() -> Organization:
    return Organization(
        id=uuid4(),
        slug=f"test-org-{uuid4().hex[:8]}",
        name="Test Org",
        status=OrganizationStatus.ACTIVE,
    )


def _make_event(org: Organization, status: EventStatus = EventStatus.DRAFT) -> Event:
    return Event(
        id=uuid4(),
        organization_id=org.id,
        slug=f"test-event-{uuid4().hex[:8]}",
        title="Test Event",
        schedule={
            "type": "single",
            "starts_at": "2026-12-31T20:00:00+03:00",
            "ends_at": "2027-01-01T03:00:00+03:00",
        },
        capacity_policy={"type": "unlimited"},
        status=status,
    )


def _valid_tariff_data(**overrides: object) -> CreateTariffInput:
    kwargs: dict = {
        "name": "VIP",
        "price_kopecks": 500000,
        "description": "VIP места",
        "capacity_limit": 50,
    }
    kwargs.update(overrides)
    return CreateTariffInput(**kwargs)


# ---------------------------------------------------------------------------
# Тесты: TariffService.create
# ---------------------------------------------------------------------------


class TestTariffServiceCreate:
    """Тесты создания тарифа."""

    async def test_create_with_valid_data(
        self, async_session: AsyncSession
    ) -> None:
        """Создание тарифа с валидными данными."""
        org = _make_org()
        event = _make_event(org)
        async_session.add_all([org, event])
        await async_session.flush()

        svc = TariffService(
            async_session,
            tariff_repo=TariffRepository(async_session),
            event_repo=EventRepository(async_session),
        )
        tariff = await svc.create(
            event.id, org.id, _valid_tariff_data()
        )

        assert tariff.name == "VIP"
        assert tariff.price_kopecks == 500000
        assert tariff.capacity_limit == 50
        assert tariff.event_id == event.id
        assert tariff.organization_id == org.id

    async def test_price_kopecks_zero_valid(
        self, async_session: AsyncSession
    ) -> None:
        """price_kopecks=0 валидно (комплиментарный билет)."""
        org = _make_org()
        event = _make_event(org)
        async_session.add_all([org, event])
        await async_session.flush()

        svc = TariffService(
            async_session,
            tariff_repo=TariffRepository(async_session),
            event_repo=EventRepository(async_session),
        )
        tariff = await svc.create(
            event.id, org.id, _valid_tariff_data(price_kopecks=0)
        )
        assert tariff.price_kopecks == 0

    async def test_price_kopecks_negative_invalid(
        self, async_session: AsyncSession
    ) -> None:
        """Отрицательная цена невалидна."""
        org = _make_org()
        event = _make_event(org)
        async_session.add_all([org, event])
        await async_session.flush()

        svc = TariffService(
            async_session,
            tariff_repo=TariffRepository(async_session),
            event_repo=EventRepository(async_session),
        )
        with pytest.raises(ValueError, match="price_kopecks"):
            await svc.create(
                event.id, org.id, _valid_tariff_data(price_kopecks=-100)
            )

    async def test_capacity_limit_negative_invalid(
        self, async_session: AsyncSession
    ) -> None:
        """Отрицательный capacity_limit невалиден."""
        org = _make_org()
        event = _make_event(org)
        async_session.add_all([org, event])
        await async_session.flush()

        svc = TariffService(
            async_session,
            tariff_repo=TariffRepository(async_session),
            event_repo=EventRepository(async_session),
        )
        with pytest.raises(ValueError, match="capacity_limit"):
            await svc.create(
                event.id, org.id, _valid_tariff_data(capacity_limit=-1)
            )

    async def test_create_for_archived_event_raises(
        self, async_session: AsyncSession
    ) -> None:
        """Нельзя создать тариф для archived события."""
        org = _make_org()
        event = _make_event(org, EventStatus.ARCHIVED)
        async_session.add_all([org, event])
        await async_session.flush()

        svc = TariffService(
            async_session,
            tariff_repo=TariffRepository(async_session),
            event_repo=EventRepository(async_session),
        )
        with pytest.raises(EventNotEditableForTariffError):
            await svc.create(event.id, org.id, _valid_tariff_data())

    async def test_create_for_rejected_event_raises(
        self, async_session: AsyncSession
    ) -> None:
        """Нельзя создать тариф для rejected события."""
        org = _make_org()
        event = _make_event(org, EventStatus.REJECTED)
        async_session.add_all([org, event])
        await async_session.flush()

        svc = TariffService(
            async_session,
            tariff_repo=TariffRepository(async_session),
            event_repo=EventRepository(async_session),
        )
        with pytest.raises(EventNotEditableForTariffError):
            await svc.create(event.id, org.id, _valid_tariff_data())

    async def test_create_for_published_event_succeeds(
        self, async_session: AsyncSession
    ) -> None:
        """Можно создать тариф для published события."""
        org = _make_org()
        event = _make_event(org, EventStatus.PUBLISHED)
        async_session.add_all([org, event])
        await async_session.flush()

        svc = TariffService(
            async_session,
            tariff_repo=TariffRepository(async_session),
            event_repo=EventRepository(async_session),
        )
        tariff = await svc.create(event.id, org.id, _valid_tariff_data())
        assert tariff.name == "VIP"


# ---------------------------------------------------------------------------
# Тесты: TariffService.update
# ---------------------------------------------------------------------------


class TestTariffServiceUpdate:
    """Тесты обновления тарифа."""

    async def _create_tariff(
        self, session: AsyncSession, event: Event, org: Organization
    ) -> Tariff:
        svc = TariffService(
            session,
            tariff_repo=TariffRepository(session),
            event_repo=EventRepository(session),
        )
        return await svc.create(event.id, org.id, _valid_tariff_data())

    async def test_update_price_forbidden_if_tickets_sold(
        self, async_session: AsyncSession
    ) -> None:
        """Нельзя менять price_kopecks если sold_count > 0."""
        org = _make_org()
        event = _make_event(org)
        async_session.add_all([org, event])
        await async_session.flush()

        tariff = await self._create_tariff(async_session, event, org)
        # Создаём reservation и reservation_item для имитации проданных билетов
        from paytools.db.models.reservation import Reservation, ReservationItem
        reservation = Reservation(
            id=uuid4(),
            organization_id=org.id,
            event_id=event.id,
            first_name="Test",
            last_name="User",
            email="test@example.com",
            phone="+79991234567",
            items_subtotal_kopecks=tariff.price_kopecks,
            discount_kopecks=0,
            total_kopecks=tariff.price_kopecks,
            status="paid",
            consent_privacy=True,
            consent_offer=True,
        )
        async_session.add(reservation)
        await async_session.flush()

        item = ReservationItem(
            id=uuid4(),
            reservation_id=reservation.id,
            tariff_id=tariff.id,
            quantity=1,
            price_kopecks=tariff.price_kopecks,
            subtotal_kopecks=tariff.price_kopecks,
        )
        async_session.add(item)
        await async_session.flush()

        svc = TariffService(
            async_session,
            tariff_repo=TariffRepository(async_session),
            event_repo=EventRepository(async_session),
        )
        with pytest.raises(TariffPriceLockedError):
            await svc.update(
                tariff.id, UpdateTariffInput(price_kopecks=600000)
            )

    async def test_update_price_allowed_if_no_tickets_sold(
        self, async_session: AsyncSession
    ) -> None:
        """Можно менять price_kopecks если sold_count == 0."""
        org = _make_org()
        event = _make_event(org)
        async_session.add_all([org, event])
        await async_session.flush()

        tariff = await self._create_tariff(async_session, event, org)

        svc = TariffService(
            async_session,
            tariff_repo=TariffRepository(async_session),
            event_repo=EventRepository(async_session),
        )
        updated = await svc.update(
            tariff.id, UpdateTariffInput(price_kopecks=600000)
        )
        assert updated.price_kopecks == 600000

    async def test_update_name_allowed(
        self, async_session: AsyncSession
    ) -> None:
        """Название тарифа можно менять всегда."""
        org = _make_org()
        event = _make_event(org)
        async_session.add_all([org, event])
        await async_session.flush()

        tariff = await self._create_tariff(async_session, event, org)

        svc = TariffService(
            async_session,
            tariff_repo=TariffRepository(async_session),
            event_repo=EventRepository(async_session),
        )
        updated = await svc.update(
            tariff.id, UpdateTariffInput(name="Super VIP")
        )
        assert updated.name == "Super VIP"

    async def test_update_description_allowed(
        self, async_session: AsyncSession
    ) -> None:
        """Описание тарифа можно менять всегда."""
        org = _make_org()
        event = _make_event(org)
        async_session.add_all([org, event])
        await async_session.flush()

        tariff = await self._create_tariff(async_session, event, org)

        svc = TariffService(
            async_session,
            tariff_repo=TariffRepository(async_session),
            event_repo=EventRepository(async_session),
        )
        updated = await svc.update(
            tariff.id, UpdateTariffInput(description="New description")
        )
        assert updated.description == "New description"


# ---------------------------------------------------------------------------
# Тесты: TariffService.delete
# ---------------------------------------------------------------------------


class TestTariffServiceDelete:
    """Тесты удаления тарифа."""

    async def _create_tariff(
        self, session: AsyncSession, event: Event, org: Organization
    ) -> Tariff:
        svc = TariffService(
            session,
            tariff_repo=TariffRepository(session),
            event_repo=EventRepository(session),
        )
        return await svc.create(event.id, org.id, _valid_tariff_data())

    async def test_hard_delete_if_no_tickets_sold(
        self, async_session: AsyncSession
    ) -> None:
        """Жёсткое удаление если sold_count == 0."""
        org = _make_org()
        event = _make_event(org)
        async_session.add_all([org, event])
        await async_session.flush()

        tariff = await self._create_tariff(async_session, event, org)

        svc = TariffService(
            async_session,
            tariff_repo=TariffRepository(async_session),
            event_repo=EventRepository(async_session),
        )
        result = await svc.delete(tariff.id)
        assert result["method"] == "hard"
        assert result["deleted"] is True

        # Проверяем что тариф удалён из БД
        repo = TariffRepository(async_session)
        deleted = await repo.get(tariff.id)
        assert deleted is None

    async def test_soft_delete_if_tickets_sold(
        self, async_session: AsyncSession
    ) -> None:
        """Мягкое удаление (is_active=false) если sold_count > 0."""
        org = _make_org()
        event = _make_event(org)
        async_session.add_all([org, event])
        await async_session.flush()

        tariff = await self._create_tariff(async_session, event, org)

        # Создаём reservation и reservation_item для имитации проданных билетов
        from paytools.db.models.reservation import Reservation, ReservationItem
        reservation = Reservation(
            id=uuid4(),
            organization_id=org.id,
            event_id=event.id,
            first_name="Test",
            last_name="User",
            email="test@example.com",
            phone="+79991234567",
            items_subtotal_kopecks=tariff.price_kopecks,
            discount_kopecks=0,
            total_kopecks=tariff.price_kopecks,
            status="paid",
            consent_privacy=True,
            consent_offer=True,
        )
        async_session.add(reservation)
        await async_session.flush()

        item = ReservationItem(
            id=uuid4(),
            reservation_id=reservation.id,
            tariff_id=tariff.id,
            quantity=1,
            price_kopecks=tariff.price_kopecks,
            subtotal_kopecks=tariff.price_kopecks,
        )
        async_session.add(item)
        await async_session.flush()

        svc = TariffService(
            async_session,
            tariff_repo=TariffRepository(async_session),
            event_repo=EventRepository(async_session),
        )
        result = await svc.delete(tariff.id)
        assert result["method"] == "soft"
        assert result["deleted"] is True

        # Проверяем что тариф остался в БД но is_active=false
        repo = TariffRepository(async_session)
        soft_deleted = await repo.get(tariff.id)
        assert soft_deleted is not None
        assert soft_deleted.is_active is False