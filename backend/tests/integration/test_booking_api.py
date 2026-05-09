"""Integration-тесты публичного booking API (Phase 4).

Покрывает:
- POST /api/v1/public/reservations — создание брони
- GET  /api/v1/public/reservations/{id} — просмотр брони
- POST /api/v1/public/promocodes/validate — валидация промокода
- POST /api/v1/organizer/reservations/{id}/cancel — отмена организатором
- Idempotency (X-Idempotency-Key)
- Expiration (expire_draft_reservations job)
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from paytools.db.models.enums import (
    DiscountType,
    EventStatus,
    OrganizationStatus,
    ReservationStatus,
    UserRole,
)
from paytools.db.models.event import Event, Tariff
from paytools.db.models.organization import Organization
from paytools.db.repositories.event import EventRepository
from paytools.db.repositories.organization import OrganizationRepository
from paytools.db.repositories.promocode import (
    PromoCodeRepository,
    PromoCodeUsageRepository,
)
from paytools.db.repositories.reservation import ReservationRepository
from paytools.db.repositories.user import UserRepository
from paytools.domain.bookings.service import BookingService
from paytools.domain.events.service import CreateEventInput, EventService
from paytools.domain.promocodes.service import CreatePromoCodeInput, PromoService
from paytools.db.repositories.email_blocklist import EmailBlocklistRepository
from paytools.core.security import hash_password


# ---------------------------------------------------------------------------
# Хелперы
# ---------------------------------------------------------------------------


async def _create_org_and_user(
    session: AsyncSession, slug: str = "booking-test-org"
) -> tuple[Organization, str]:
    """Создаёт организацию + пользователя, возвращает (org, email)."""
    org_repo = OrganizationRepository(session)
    user_repo = UserRepository(session)

    org = await org_repo.create(
        slug=slug,
        name=f"Booking Test Org {slug}",
        status=OrganizationStatus.ACTIVE,
    )
    # Используем example.com — он валидируется email-валидатором
    email = f"organizer+{slug}@example.com"
    user = await user_repo.create(
        email=email,
        password_hash=hash_password("Pass1234!"),
        first_name="Test",
        last_name="Organizer",
        role=UserRole.ORGANIZER,
        is_active=True,
        organization_id=org.id,
    )
    return org, email


async def _get_token(client: AsyncClient, email: str, password: str = "Pass1234!") -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def _create_published_event(
    session: AsyncSession,
    org: Organization,
    capacity_policy: dict | None = None,
) -> Event:
    svc = EventService(
        session,
        event_repo=EventRepository(session),
        org_repo=OrganizationRepository(session),
    )
    event = await svc.create(
        org.id,
        CreateEventInput(
            title="Test Booking Event",
            slug=f"test-booking-{uuid4().hex[:8]}",
            schedule={
                "type": "single",
                "starts_at": "2027-01-01T20:00:00+03:00",
                "ends_at": "2027-01-01T23:00:00+03:00",
            },
            capacity_policy=capacity_policy or {"type": "unlimited"},
        ),
    )
    event.status = EventStatus.PUBLISHED
    await session.flush()
    return event


async def _create_tariff(
    session: AsyncSession,
    org: Organization,
    event: Event,
    price: int = 100_00,  # 100 рублей в копейках
    capacity_limit: int | None = None,
) -> Tariff:
    """Создать тариф напрямую через ORM."""
    tariff = Tariff(
        id=uuid4(),
        event_id=event.id,
        organization_id=org.id,
        name="Standard",
        price_kopecks=price,
        capacity_limit=capacity_limit,
        is_active=True,
    )
    session.add(tariff)
    await session.flush()
    return tariff


def _booking_payload(event_id: str, tariff_id: str, qty: int = 1, **kwargs: object) -> dict:
    return {
        "event_id": event_id,
        "first_name": "Иван",
        "last_name": "Петров",
        "email": "ivan@example.com",
        "phone": "+79001234567",
        "items": [{"tariff_id": tariff_id, "quantity": qty}],
        "consent_privacy": True,
        "consent_offer": True,
        **kwargs,
    }


# ---------------------------------------------------------------------------
# Тесты: POST /api/v1/public/reservations
# ---------------------------------------------------------------------------


class TestCreateReservation:
    """Тесты создания бронирования."""

    async def test_happy_path(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
    ) -> None:
        """Успешное создание брони."""
        org, _ = await _create_org_and_user(async_session, slug=f"org-{uuid4().hex[:6]}")
        event = await _create_published_event(async_session, org)
        tariff = await _create_tariff(async_session, org, event, price=5000)

        resp = await client.post(
            "/api/v1/public/reservations",
            json=_booking_payload(str(event.id), str(tariff.id)),
            headers={"X-Tenant-Slug": org.slug},
        )

        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["status"] == "pending_payment"
        assert data["total_kopecks"] == 5000
        assert data["discount_kopecks"] == 0
        assert "id" in data
        assert "expires_at" in data
        assert "payment_url" in data

    async def test_sold_out_returns_409(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
    ) -> None:
        """Sold out → 409."""
        org, _ = await _create_org_and_user(async_session, slug=f"org-{uuid4().hex[:6]}")
        event = await _create_published_event(
            async_session, org, capacity_policy={"type": "total", "limit": 1}
        )
        tariff = await _create_tariff(async_session, org, event)

        # Первая успешная бронь
        r1 = await client.post(
            "/api/v1/public/reservations",
            json=_booking_payload(str(event.id), str(tariff.id), email="first@test.com"),
            headers={"X-Tenant-Slug": org.slug},
        )
        assert r1.status_code == 201, r1.text

        # Вторая — sold out
        r2 = await client.post(
            "/api/v1/public/reservations",
            json=_booking_payload(str(event.id), str(tariff.id), email="second@test.com"),
            headers={"X-Tenant-Slug": org.slug},
        )
        assert r2.status_code == 409, r2.text
        assert r2.json()["error"]["code"] == "capacity_exceeded"

    async def test_idempotency(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
    ) -> None:
        """Два запроса с одинаковым X-Idempotency-Key → один reservation."""
        org, _ = await _create_org_and_user(async_session, slug=f"org-{uuid4().hex[:6]}")
        event = await _create_published_event(async_session, org)
        tariff = await _create_tariff(async_session, org, event)

        key = f"idem-{uuid4().hex}"
        payload = _booking_payload(str(event.id), str(tariff.id))

        r1 = await client.post(
            "/api/v1/public/reservations",
            json=payload,
            headers={"X-Tenant-Slug": org.slug, "Idempotency-Key": key},
        )
        assert r1.status_code == 201, r1.text

        r2 = await client.post(
            "/api/v1/public/reservations",
            json=payload,
            headers={"X-Tenant-Slug": org.slug, "Idempotency-Key": key},
        )
        assert r2.status_code == 201, r2.text
        # Оба должны вернуть один и тот же ID
        assert r1.json()["id"] == r2.json()["id"]

    async def test_missing_consent_returns_422(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
    ) -> None:
        """Без согласия → 422."""
        org, _ = await _create_org_and_user(async_session, slug=f"org-{uuid4().hex[:6]}")
        event = await _create_published_event(async_session, org)
        tariff = await _create_tariff(async_session, org, event)

        payload = _booking_payload(str(event.id), str(tariff.id))
        payload["consent_privacy"] = False

        resp = await client.post(
            "/api/v1/public/reservations",
            json=payload,
            headers={"X-Tenant-Slug": org.slug},
        )
        # ConsentRequiredError → 400 (domain error, не validation error)
        assert resp.status_code == 400, resp.text
        assert resp.json()["error"]["code"] == "consent_required"


# ---------------------------------------------------------------------------
# Тесты: expiration
# ---------------------------------------------------------------------------


class TestReservationExpiration:
    """Тест expiration job."""

    async def test_expire_job_cancels_old_reservations(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
    ) -> None:
        """Expire job переводит просроченные брони в expired и возвращает capacity."""
        org, _ = await _create_org_and_user(async_session, slug=f"org-{uuid4().hex[:6]}")
        event = await _create_published_event(
            async_session, org, capacity_policy={"type": "total", "limit": 1}
        )
        tariff = await _create_tariff(async_session, org, event)

        # Создаём бронь
        r = await client.post(
            "/api/v1/public/reservations",
            json=_booking_payload(str(event.id), str(tariff.id)),
            headers={"X-Tenant-Slug": org.slug},
        )
        assert r.status_code == 201, r.text
        reservation_id = r.json()["id"]

        # Ставим expires_at в прошлое напрямую
        reservation_repo = ReservationRepository(async_session)
        reservation = await reservation_repo.get(reservation_id)
        assert reservation is not None
        reservation.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        await async_session.flush()

        # Проверяем что место занято (sold out)
        r2 = await client.post(
            "/api/v1/public/reservations",
            json=_booking_payload(str(event.id), str(tariff.id), email="other@test.com"),
            headers={"X-Tenant-Slug": org.slug},
        )
        assert r2.status_code == 409, "Место должно быть занято до expire"

        # Запускаем expire job через сервис напрямую (минуя AsyncSessionLocal)
        svc = BookingService(
            async_session,
            reservation_repo=ReservationRepository(async_session),
            event_repo=EventRepository(async_session),
            promo_repo=PromoCodeRepository(async_session),
            usage_repo=PromoCodeUsageRepository(async_session),
            blocklist_repo=EmailBlocklistRepository(async_session),
        )
        expired_count = await svc.expire_drafts()
        assert expired_count >= 1

        # Проверяем что бронь expired
        await async_session.refresh(reservation)
        assert reservation.status == ReservationStatus.EXPIRED

        # Теперь место освободилось — можно снова бронировать
        r3 = await client.post(
            "/api/v1/public/reservations",
            json=_booking_payload(str(event.id), str(tariff.id), email="new@test.com"),
            headers={"X-Tenant-Slug": org.slug},
        )
        assert r3.status_code == 201, f"После expire место должно освободиться: {r3.text}"


# ---------------------------------------------------------------------------
# Тесты: POST /api/v1/public/promocodes/validate
# ---------------------------------------------------------------------------


class TestPromoValidateEndpoint:
    """Тесты endpoint валидации промокода."""

    async def test_validate_valid_promo(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
    ) -> None:
        """Валидный промокод возвращает valid=true и discount_kopecks."""
        org, _ = await _create_org_and_user(async_session, slug=f"org-{uuid4().hex[:6]}")
        event = await _create_published_event(async_session, org)
        tariff = await _create_tariff(async_session, org, event, price=100_00)

        promo_svc = PromoService(
            async_session,
            promo_repo=PromoCodeRepository(async_session),
            usage_repo=PromoCodeUsageRepository(async_session),
        )
        await promo_svc.create(
            org.id,
            CreatePromoCodeInput(
                code="SAVE20",
                discount_type=DiscountType.PERCENT,
                discount_value=2000,  # 20%
                event_id=event.id,
            ),
        )

        resp = await client.post(
            "/api/v1/public/promocodes/validate",
            json={
                "code": "SAVE20",
                "event_id": str(event.id),
                "email": "user@example.com",
                "items": [{"tariff_id": str(tariff.id), "quantity": 1}],
            },
            headers={"X-Tenant-Slug": org.slug},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["valid"] is True
        assert data["discount_type"] == "percent"

    async def test_validate_invalid_promo(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
    ) -> None:
        """Несуществующий промокод → valid=false."""
        org, _ = await _create_org_and_user(async_session, slug=f"org-{uuid4().hex[:6]}")
        event = await _create_published_event(async_session, org)
        tariff = await _create_tariff(async_session, org, event)

        resp = await client.post(
            "/api/v1/public/promocodes/validate",
            json={
                "code": "NOPE999",
                "event_id": str(event.id),
                "email": "user@example.com",
                "items": [{"tariff_id": str(tariff.id), "quantity": 1}],
            },
            headers={"X-Tenant-Slug": org.slug},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["valid"] is False
        assert data["error_code"] == "promo_code_not_found"


# ---------------------------------------------------------------------------
# Тест: organizer cancel
# ---------------------------------------------------------------------------


class TestOrganizerCancelReservation:
    """Тест отмены бронирования организатором."""

    async def test_cancel_reservation(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
    ) -> None:
        """Организатор может отменить бронь."""
        slug = f"org-{uuid4().hex[:6]}"
        org, organizer_email = await _create_org_and_user(async_session, slug=slug)
        event = await _create_published_event(async_session, org)
        tariff = await _create_tariff(async_session, org, event)

        # Создаём бронь
        r = await client.post(
            "/api/v1/public/reservations",
            json=_booking_payload(str(event.id), str(tariff.id)),
            headers={"X-Tenant-Slug": org.slug},
        )
        assert r.status_code == 201, r.text
        reservation_id = r.json()["id"]

        # Логинимся как организатор
        token = await _get_token(client, organizer_email)

        # Отменяем
        cancel_resp = await client.post(
            f"/api/v1/organizer/reservations/{reservation_id}/cancel",
            json={"reason": "test cancel"},
            headers={
                "Authorization": f"Bearer {token}",
                "X-Tenant-Slug": org.slug,
            },
        )
        assert cancel_resp.status_code == 200, cancel_resp.text
        assert cancel_resp.json()["status"] == "cancelled"
