"""Unit-тесты PromoService: валидация, создание, CRUD промокодов.

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
)
from paytools.db.models.event import Event, Tariff
from paytools.db.models.organization import Organization
from paytools.db.repositories.promocode import (
    PromoCodeRepository,
    PromoCodeUsageRepository,
)
from paytools.domain.promocodes.errors import (
    PromoCodeDuplicateError,
    PromoCodeExpiredError,
    PromoCodeInactiveError,
    PromoCodeNotFoundError,
    PromoCodeUsageLimitError,
)
from paytools.domain.promocodes.service import (
    CreatePromoCodeInput,
    PromoService,
    ReservationItemInput,
    UpdatePromoCodeInput,
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


def _make_event(org: Organization) -> Event:
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
        status=EventStatus.PUBLISHED,
    )


def _make_tariff(event: Event, org: Organization) -> Tariff:
    return Tariff(
        id=uuid4(),
        event_id=event.id,
        organization_id=org.id,
        name="Standard",
        price_kopecks=100000,
        is_active=True,
    )


def _svc(session: AsyncSession) -> PromoService:
    return PromoService(
        session,
        promo_repo=PromoCodeRepository(session),
        usage_repo=PromoCodeUsageRepository(session),
    )


# ---------------------------------------------------------------------------
# Тесты: PromoService.create
# ---------------------------------------------------------------------------


class TestPromoServiceCreate:
    """Тесты создания промокода."""

    async def test_create_valid(self, async_session: AsyncSession) -> None:
        """Создание промокода с валидными данными."""
        org = _make_org()
        async_session.add(org)
        await async_session.flush()

        svc = _svc(async_session)
        promo = await svc.create(
            org.id,
            CreatePromoCodeInput(
                code="HELLO10",
                discount_type=DiscountType.PERCENT,
                discount_value=1000,  # 10%
            ),
        )

        assert promo.code == "HELLO10"
        assert promo.discount_type == DiscountType.PERCENT
        assert promo.discount_value == 1000
        assert promo.organization_id == org.id
        assert promo.is_active is True

    async def test_create_duplicate_raises(
        self, async_session: AsyncSession
    ) -> None:
        """Нельзя создать два промокода с одинаковым кодом в организации."""
        org = _make_org()
        async_session.add(org)
        await async_session.flush()

        svc = _svc(async_session)
        await svc.create(
            org.id,
            CreatePromoCodeInput(
                code="DUP",
                discount_type=DiscountType.FIXED_AMOUNT,
                discount_value=5000,
            ),
        )

        with pytest.raises(PromoCodeDuplicateError):
            await svc.create(
                org.id,
                CreatePromoCodeInput(
                    code="dup",  # case-insensitive!
                    discount_type=DiscountType.FIXED_AMOUNT,
                    discount_value=5000,
                ),
            )


# ---------------------------------------------------------------------------
# Тесты: PromoService.validate
# ---------------------------------------------------------------------------


class TestPromoServiceValidate:
    """Тесты валидации промокода."""

    async def test_valid_promo(self, async_session: AsyncSession) -> None:
        """Валидный промокод возвращает discount_kopecks."""
        org = _make_org()
        event = _make_event(org)
        tariff = _make_tariff(event, org)
        async_session.add_all([org, event, tariff])
        await async_session.flush()

        svc = _svc(async_session)
        await svc.create(
            org.id,
            CreatePromoCodeInput(
                code="SAVE10",
                discount_type=DiscountType.PERCENT,
                discount_value=1000,  # 10% (×100)
                event_id=event.id,
            ),
        )

        result = await svc.validate(
            org_id=org.id,
            code="SAVE10",
            event_id=event.id,
            email="user@example.com",
            items=[
                ReservationItemInput(
                    tariff_id=tariff.id,
                    quantity=2,
                    price_kopecks=100000,
                ),
            ],
        )

        assert result.valid is True
        # 10% от (2 * 100000) = 20000
        assert result.discount_kopecks == 20000

    async def test_not_found(self, async_session: AsyncSession) -> None:
        """Несуществующий промокод."""
        org = _make_org()
        event = _make_event(org)
        async_session.add_all([org, event])
        await async_session.flush()

        svc = _svc(async_session)
        result = await svc.validate(
            org_id=org.id,
            code="NOPE",
            event_id=event.id,
            email="user@example.com",
            items=[],
        )
        assert result.valid is False
        assert result.error_code == "promo_code_not_found"

    async def test_inactive_promo(self, async_session: AsyncSession) -> None:
        """Деактивированный промокод."""
        org = _make_org()
        event = _make_event(org)
        async_session.add_all([org, event])
        await async_session.flush()

        svc = _svc(async_session)
        await svc.create(
            org.id,
            CreatePromoCodeInput(
                code="OFF",
                discount_type=DiscountType.PERCENT,
                discount_value=500,
                is_active=False,
            ),
        )

        result = await svc.validate(
            org_id=org.id,
            code="OFF",
            event_id=event.id,
            email="user@example.com",
            items=[],
        )
        assert result.valid is False
        assert result.error_code == "promo_code_inactive"

    async def test_expired_promo(self, async_session: AsyncSession) -> None:
        """Промокод с истёкшим active_to."""
        org = _make_org()
        event = _make_event(org)
        async_session.add_all([org, event])
        await async_session.flush()

        svc = _svc(async_session)
        past = datetime.now(timezone.utc) - timedelta(days=1)
        await svc.create(
            org.id,
            CreatePromoCodeInput(
                code="OLD",
                discount_type=DiscountType.PERCENT,
                discount_value=500,
                active_to=past,
            ),
        )

        result = await svc.validate(
            org_id=org.id,
            code="OLD",
            event_id=event.id,
            email="user@example.com",
            items=[],
        )
        assert result.valid is False
        assert result.error_code == "promo_code_expired"

    async def test_wrong_event(self, async_session: AsyncSession) -> None:
        """Промокод привязан к другому событию."""
        org = _make_org()
        event1 = _make_event(org)
        event2 = _make_event(org)
        async_session.add_all([org, event1, event2])
        await async_session.flush()

        svc = _svc(async_session)
        await svc.create(
            org.id,
            CreatePromoCodeInput(
                code="E1ONLY",
                discount_type=DiscountType.PERCENT,
                discount_value=500,
                event_id=event1.id,
            ),
        )

        result = await svc.validate(
            org_id=org.id,
            code="E1ONLY",
            event_id=event2.id,  # Другое событие
            email="user@example.com",
            items=[],
        )
        assert result.valid is False
        assert result.error_code == "promo_code_wrong_event"


# ---------------------------------------------------------------------------
# Тесты: скидка fixed_amount
# ---------------------------------------------------------------------------


class TestPromoDiscountCalculation:
    """Тесты расчёта скидки."""

    async def test_fixed_amount(self, async_session: AsyncSession) -> None:
        """fixed_amount не может превышать subtotal."""
        org = _make_org()
        event = _make_event(org)
        tariff = _make_tariff(event, org)
        async_session.add_all([org, event, tariff])
        await async_session.flush()

        svc = _svc(async_session)
        await svc.create(
            org.id,
            CreatePromoCodeInput(
                code="BIG",
                discount_type=DiscountType.FIXED_AMOUNT,
                discount_value=9999999,  # Больше subtotal
            ),
        )

        result = await svc.validate(
            org_id=org.id,
            code="BIG",
            event_id=event.id,
            email="user@example.com",
            items=[
                ReservationItemInput(
                    tariff_id=tariff.id,
                    quantity=1,
                    price_kopecks=100000,
                ),
            ],
        )
        assert result.valid is True
        assert result.discount_kopecks == 100000  # min(9999999, 100000)


# ---------------------------------------------------------------------------
# Тесты: PromoService.update
# ---------------------------------------------------------------------------


class TestPromoServiceUpdate:
    """Тесты обновления промокода."""

    async def test_update_is_active(
        self, async_session: AsyncSession
    ) -> None:
        """Деактивация промокода через update."""
        org = _make_org()
        async_session.add(org)
        await async_session.flush()

        svc = _svc(async_session)
        promo = await svc.create(
            org.id,
            CreatePromoCodeInput(
                code="UPD",
                discount_type=DiscountType.PERCENT,
                discount_value=500,
            ),
        )
        assert promo.is_active is True

        updated = await svc.update(
            promo.id,
            UpdatePromoCodeInput(is_active=False),
        )
        assert updated.is_active is False

    async def test_update_nonexistent_raises(
        self, async_session: AsyncSession
    ) -> None:
        """Обновление несуществующего промокода."""
        org = _make_org()
        async_session.add(org)
        await async_session.flush()

        svc = _svc(async_session)
        with pytest.raises(PromoCodeNotFoundError):
            await svc.update(
                uuid4(),
                UpdatePromoCodeInput(is_active=False),
            )
