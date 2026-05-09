"""Race condition тест: атомарность capacity check.

50 конкурентных запросов на event с capacity_limit=10 →
ровно 10 успешных, 40 с CapacityExceededError.

Тестирует БД-уровень через прямые вызовы BookingService
с отдельными сессиями на каждый конкурентный запрос.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from paytools.db.models.enums import EventStatus, OrganizationStatus
from paytools.db.models.event import Event, Tariff
from paytools.db.models.organization import Organization
from paytools.db.repositories.email_blocklist import EmailBlocklistRepository
from paytools.db.repositories.event import EventRepository
from paytools.db.repositories.promocode import (
    PromoCodeRepository,
    PromoCodeUsageRepository,
)
from paytools.db.repositories.reservation import ReservationRepository
from paytools.domain.bookings.errors import CapacityExceededError
from paytools.domain.bookings.service import (
    BookingService,
    CreateReservationInput,
    ReservationItemData,
)


def _make_org(slug: str) -> Organization:
    return Organization(
        id=uuid4(),
        slug=slug,
        name=f"Race Org {slug}",
        status=OrganizationStatus.ACTIVE,
    )


def _make_event(org: Organization, capacity_limit: int) -> Event:
    return Event(
        id=uuid4(),
        organization_id=org.id,
        slug=f"race-event-{uuid4().hex[:8]}",
        title="Race Test Event",
        schedule={
            "type": "single",
            "starts_at": "2027-06-01T20:00:00+03:00",
            "ends_at": "2027-06-01T23:00:00+03:00",
        },
        capacity_policy={"type": "total", "limit": capacity_limit},
        status=EventStatus.PUBLISHED,
    )


def _make_tariff(event: Event, org: Organization) -> Tariff:
    return Tariff(
        id=uuid4(),
        event_id=event.id,
        organization_id=org.id,
        name="Standard",
        price_kopecks=100_00,
        is_active=True,
    )


def _make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        class_=AsyncSession,
        autoflush=False,
    )


def _build_booking_service(session: AsyncSession) -> BookingService:
    return BookingService(
        session,
        reservation_repo=ReservationRepository(session),
        event_repo=EventRepository(session),
        promo_repo=PromoCodeRepository(session),
        usage_repo=PromoCodeUsageRepository(session),
        blocklist_repo=EmailBlocklistRepository(session),
    )


@pytest.mark.slow
class TestBookingRaceCondition:
    """Race condition: capacity check атомарен на уровне БД."""

    async def test_concurrent_bookings_respect_capacity(
        self,
        async_engine: AsyncEngine,
    ) -> None:
        """50 одновременных запросов при лимите 10 → ровно 10 успешных."""
        LIMIT = 10
        CONCURRENT = 50

        slug = f"race-org-{uuid4().hex[:6]}"
        org = _make_org(slug)
        event = _make_event(org, LIMIT)
        tariff = _make_tariff(event, org)

        # Сохраняем тестовые данные в отдельной setup-сессии
        session_factory = _make_session_factory(async_engine)
        async with session_factory() as setup_session:
            async with setup_session.begin():
                setup_session.add_all([org, event, tariff])

        org_id = org.id
        event_id = event.id
        tariff_id = tariff.id

        async def make_booking(i: int) -> bool:
            """Попытаться забронировать 1 место. Возвращает True если успешно."""
            async with session_factory() as session:
                async with session.begin():
                    svc = _build_booking_service(session)
                    try:
                        await svc.create_reservation(
                            org_id=org_id,
                            data=CreateReservationInput(
                                event_id=event_id,
                                first_name="User",
                                last_name=f"Number{i}",
                                email=f"user{i}@race-test.com",
                                phone="+79001234567",
                                items=[ReservationItemData(tariff_id=tariff_id, quantity=1)],
                                consent_privacy=True,
                                consent_offer=True,
                            ),
                        )
                        return True
                    except CapacityExceededError:
                        return False

        # Запускаем все запросы одновременно
        results = await asyncio.gather(
            *[make_booking(i) for i in range(CONCURRENT)],
            return_exceptions=True,
        )

        successful = sum(1 for r in results if r is True)
        rejected = sum(1 for r in results if r is False)

        assert successful == LIMIT, (
            f"Ожидалось ровно {LIMIT} успешных, получили {successful}. "
            f"Результаты: {results}"
        )
        assert rejected == CONCURRENT - LIMIT, (
            f"Ожидалось {CONCURRENT - LIMIT} отказов, получили {rejected}"
        )

        # Проверяем sold_count в БД
        async with session_factory() as verify_session:
            result = await verify_session.execute(
                text("SELECT sold_count FROM events WHERE id = :eid"),
                {"eid": event_id},
            )
            row = result.fetchone()
            assert row is not None
            assert row[0] == LIMIT, f"sold_count должен быть {LIMIT}, а не {row[0]}"
