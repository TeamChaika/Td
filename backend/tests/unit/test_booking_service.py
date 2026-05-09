"""Unit-тесты BookingService: создание, отмена бронирований.

Использует реальную БД через async_session (транзакционный rollback).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from paytools.db.models.enums import (
    DiscountType,
    EventStatus,
    OrganizationStatus,
    ReservationStatus,
)
from paytools.db.models.event import Event, Tariff
from paytools.db.models.organization import Organization
from paytools.db.repositories.email_blocklist import EmailBlocklistRepository
from paytools.db.repositories.event import EventRepository
from paytools.db.repositories.promocode import (
    PromoCodeRepository,
    PromoCodeUsageRepository,
)
from paytools.db.repositories.reservation import ReservationRepository
from paytools.domain.bookings.errors import (
    CapacityExceededError,
    ConsentRequiredError,
    EventNotPublishedError,
    ReservationAlreadyCancelledError,
    TariffNotAvailableError,
)
from paytools.domain.bookings.service import (
    BookingService,
    CreateReservationInput,
    ReservationItemData,
)
from paytools.domain.promocodes.service import CreatePromoCodeInput, PromoService


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


def _make_event(
    org: Organization,
    status: EventStatus = EventStatus.PUBLISHED,
    capacity_policy: dict | None = None,
) -> Event:
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
        capacity_policy=capacity_policy or {"type": "unlimited"},
        status=status,
    )


def _make_tariff(
    event: Event, org: Organization, price: int = 100000
) -> Tariff:
    return Tariff(
        id=uuid4(),
        event_id=event.id,
        organization_id=org.id,
        name="Standard",
        price_kopecks=price,
        is_active=True,
    )


def _svc(session: AsyncSession) -> BookingService:
    return BookingService(
        session,
        reservation_repo=ReservationRepository(session),
        event_repo=EventRepository(session),
        promo_repo=PromoCodeRepository(session),
        usage_repo=PromoCodeUsageRepository(session),
        blocklist_repo=EmailBlocklistRepository(session),
    )


def _valid_input(
    event: Event,
    tariff: Tariff,
    **overrides: object,
) -> CreateReservationInput:
    kwargs: dict = {
        "event_id": event.id,
        "first_name": "Иван",
        "last_name": "Петров",
        "email": "ivan@example.com",
        "phone": "+79001234567",
        "items": [ReservationItemData(tariff_id=tariff.id, quantity=1)],
        "consent_privacy": True,
        "consent_offer": True,
    }
    kwargs.update(overrides)
    return CreateReservationInput(**kwargs)


# ---------------------------------------------------------------------------
# Тесты: BookingService.create_reservation
# ---------------------------------------------------------------------------


class TestBookingServiceCreate:
    """Тесты создания бронирования."""

    async def test_create_valid(self, async_session: AsyncSession) -> None:
        """Создание бронирования с валидными данными."""
        org = _make_org()
        event = _make_event(org)
        tariff = _make_tariff(event, org, price=50000)
        async_session.add_all([org, event, tariff])
        await async_session.flush()

        svc = _svc(async_session)
        reservation = await svc.create_reservation(
            org.id,
            _valid_input(event, tariff),
        )

        assert reservation.status == ReservationStatus.PENDING_PAYMENT
        assert reservation.total_kopecks == 50000
        assert reservation.items_subtotal_kopecks == 50000
        assert reservation.discount_kopecks == 0
        assert reservation.first_name == "Иван"
        assert reservation.email == "ivan@example.com"
        assert reservation.expires_at is not None

    async def test_create_multiple_items(
        self, async_session: AsyncSession
    ) -> None:
        """Создание бронирования с несколькими тарифами."""
        org = _make_org()
        event = _make_event(org)
        tariff1 = _make_tariff(event, org, price=50000)
        tariff2 = _make_tariff(event, org, price=100000)
        async_session.add_all([org, event, tariff1, tariff2])
        await async_session.flush()

        svc = _svc(async_session)
        reservation = await svc.create_reservation(
            org.id,
            CreateReservationInput(
                event_id=event.id,
                first_name="Иван",
                last_name="Петров",
                email="ivan@example.com",
                phone="+79001234567",
                items=[
                    ReservationItemData(tariff_id=tariff1.id, quantity=2),
                    ReservationItemData(tariff_id=tariff2.id, quantity=1),
                ],
                consent_privacy=True,
                consent_offer=True,
            ),
        )

        assert reservation.items_subtotal_kopecks == 200000  # 2*50000 + 1*100000
        assert reservation.total_kopecks == 200000

    async def test_consent_required(
        self, async_session: AsyncSession
    ) -> None:
        """Без согласия — ConsentRequiredError."""
        org = _make_org()
        event = _make_event(org)
        tariff = _make_tariff(event, org)
        async_session.add_all([org, event, tariff])
        await async_session.flush()

        svc = _svc(async_session)
        with pytest.raises(ConsentRequiredError):
            await svc.create_reservation(
                org.id,
                _valid_input(event, tariff, consent_privacy=False),
            )

    async def test_draft_event_not_bookable(
        self, async_session: AsyncSession
    ) -> None:
        """Нельзя бронировать draft-событие."""
        org = _make_org()
        event = _make_event(org, status=EventStatus.DRAFT)
        tariff = _make_tariff(event, org)
        async_session.add_all([org, event, tariff])
        await async_session.flush()

        svc = _svc(async_session)
        with pytest.raises(EventNotPublishedError):
            await svc.create_reservation(
                org.id,
                _valid_input(event, tariff),
            )

    async def test_wrong_tariff_raises(
        self, async_session: AsyncSession
    ) -> None:
        """Тариф от другого события."""
        org = _make_org()
        event1 = _make_event(org)
        event2 = _make_event(org)
        tariff = _make_tariff(event2, org)  # Привязан к event2
        async_session.add_all([org, event1, event2, tariff])
        await async_session.flush()

        svc = _svc(async_session)
        with pytest.raises(TariffNotAvailableError):
            await svc.create_reservation(
                org.id,
                _valid_input(event1, tariff),  # event1 + tariff от event2
            )

    async def test_idempotency(self, async_session: AsyncSession) -> None:
        """Повторный запрос с тем же idempotency_key возвращает ту же бронь."""
        org = _make_org()
        event = _make_event(org)
        tariff = _make_tariff(event, org)
        async_session.add_all([org, event, tariff])
        await async_session.flush()

        svc = _svc(async_session)
        key = f"idem-{uuid4().hex}"
        input_data = _valid_input(event, tariff, idempotency_key=key)

        r1 = await svc.create_reservation(org.id, input_data)
        r2 = await svc.create_reservation(org.id, input_data)
        assert r1.id == r2.id

    async def test_capacity_total_exceeded(
        self, async_session: AsyncSession
    ) -> None:
        """Превышение capacity (total) вызывает CapacityExceededError."""
        org = _make_org()
        event = _make_event(
            org,
            capacity_policy={"type": "total", "limit": 1},
        )
        tariff = _make_tariff(event, org)
        async_session.add_all([org, event, tariff])
        await async_session.flush()

        svc = _svc(async_session)

        # Первый билет — ок
        await svc.create_reservation(
            org.id,
            _valid_input(event, tariff, email="first@example.com"),
        )

        # Второй — sold out
        with pytest.raises(CapacityExceededError):
            await svc.create_reservation(
                org.id,
                _valid_input(event, tariff, email="second@example.com"),
            )


# ---------------------------------------------------------------------------
# Тесты: BookingService.cancel
# ---------------------------------------------------------------------------


class TestBookingServiceCancel:
    """Тесты отмены бронирования."""

    async def test_cancel_pending(
        self, async_session: AsyncSession
    ) -> None:
        """Отмена pending_payment бронирования."""
        org = _make_org()
        event = _make_event(org)
        tariff = _make_tariff(event, org)
        async_session.add_all([org, event, tariff])
        await async_session.flush()

        svc = _svc(async_session)
        reservation = await svc.create_reservation(
            org.id,
            _valid_input(event, tariff),
        )

        cancelled = await svc.cancel(reservation.id, reason="test reason")
        assert cancelled.status == ReservationStatus.CANCELLED
        assert cancelled.cancel_reason == "test reason"

    async def test_cancel_twice_raises(
        self, async_session: AsyncSession
    ) -> None:
        """Повторная отмена — ReservationAlreadyCancelledError."""
        org = _make_org()
        event = _make_event(org)
        tariff = _make_tariff(event, org)
        async_session.add_all([org, event, tariff])
        await async_session.flush()

        svc = _svc(async_session)
        reservation = await svc.create_reservation(
            org.id,
            _valid_input(event, tariff),
        )

        await svc.cancel(reservation.id)
        with pytest.raises(ReservationAlreadyCancelledError):
            await svc.cancel(reservation.id)

    async def test_cancel_releases_capacity(
        self, async_session: AsyncSession
    ) -> None:
        """После отмены capacity освобождается — можно бронировать снова."""
        org = _make_org()
        event = _make_event(
            org,
            capacity_policy={"type": "total", "limit": 1},
        )
        tariff = _make_tariff(event, org)
        async_session.add_all([org, event, tariff])
        await async_session.flush()

        svc = _svc(async_session)

        # Бронируем единственное место
        r1 = await svc.create_reservation(
            org.id,
            _valid_input(event, tariff, email="first@example.com"),
        )

        # Пробуем ещё — sold out
        with pytest.raises(CapacityExceededError):
            await svc.create_reservation(
                org.id,
                _valid_input(event, tariff, email="second@example.com"),
            )

        # Отменяем первую
        await svc.cancel(r1.id)

        # Теперь можно опять забронировать
        r2 = await svc.create_reservation(
            org.id,
            _valid_input(event, tariff, email="third@example.com"),
        )
        assert r2.status == ReservationStatus.PENDING_PAYMENT


# ---------------------------------------------------------------------------
# Тесты: BookingService.create_reservation с промокодом
# ---------------------------------------------------------------------------


class TestBookingWithPromo:
    """Тесты бронирования с промокодом."""

    async def test_create_with_valid_promo(
        self, async_session: AsyncSession
    ) -> None:
        """Бронирование с валидным промокодом применяет скидку."""
        org = _make_org()
        event = _make_event(org)
        tariff = _make_tariff(event, org, price=100000)
        async_session.add_all([org, event, tariff])
        await async_session.flush()

        # Создаём промокод 10%
        promo_svc = PromoService(
            async_session,
            promo_repo=PromoCodeRepository(async_session),
            usage_repo=PromoCodeUsageRepository(async_session),
        )
        await promo_svc.create(
            org.id,
            CreatePromoCodeInput(
                code="SAVE10",
                discount_type=DiscountType.PERCENT,
                discount_value=1000,  # 10%
            ),
        )

        svc = _svc(async_session)
        reservation = await svc.create_reservation(
            org.id,
            _valid_input(event, tariff, promo_code="SAVE10"),
        )

        assert reservation.discount_kopecks == 10000  # 10% от 100000
        assert reservation.total_kopecks == 90000  # 100000 - 10000
        assert reservation.promo_code_id is not None
