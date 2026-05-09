"""Integration-тесты payment API (Phase 5).

Покрывает:
- GET  /api/v1/public/payments/{id}/status
- POST /api/v1/organizer/reservations/{id}/mark-paid
- POST /api/v1/organizer/reservations/{id}/complimentary
- Выпуск билетов после оплаты
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from paytools.db.models.enums import (
    EventStatus,
    OrganizationStatus,
    ReservationStatus,
    TicketStatus,
    UserRole,
)
from paytools.db.models.event import Event, Tariff
from paytools.db.models.organization import Organization
from paytools.db.models.reservation import Reservation, ReservationItem
from paytools.db.repositories.organization import OrganizationRepository
from paytools.db.repositories.user import UserRepository
from paytools.core.security import hash_password
from paytools.domain.events.service import CreateEventInput, EventService
from paytools.db.repositories.event import EventRepository


# ---------------------------------------------------------------------------
# Хелперы
# ---------------------------------------------------------------------------


async def _create_org_and_user(
    session: AsyncSession, slug: str
) -> tuple[Organization, str]:
    org_repo = OrganizationRepository(session)
    user_repo = UserRepository(session)

    org = await org_repo.create(
        slug=slug,
        name=f"Payment Test Org {slug}",
        status=OrganizationStatus.ACTIVE,
    )
    email = f"organizer+{slug}@example.com"
    await user_repo.create(
        email=email,
        password_hash=hash_password("Pass1234!"),
        first_name="Test",
        last_name="Organizer",
        role=UserRole.ORGANIZER,
        is_active=True,
        organization_id=org.id,
    )
    return org, email


async def _get_token(client: AsyncClient, email: str) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Pass1234!"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def _setup_reservation(
    session: AsyncSession,
    org: Organization,
    status: ReservationStatus = ReservationStatus.PENDING_PAYMENT,
    price: int = 100_00,
) -> tuple[Reservation, str]:
    """Создать событие, тариф и бронь. Возвращает (reservation, tariff_id)."""
    # Создаём published event
    svc = EventService(
        session,
        event_repo=EventRepository(session),
        org_repo=OrganizationRepository(session),
    )
    event = await svc.create(
        org.id,
        CreateEventInput(
            title=f"Payment Test {uuid4().hex[:6]}",
            slug=f"pay-test-{uuid4().hex[:8]}",
            schedule={
                "type": "single",
                "starts_at": "2027-06-01T20:00:00+03:00",
                "ends_at": "2027-06-01T23:00:00+03:00",
            },
            capacity_policy={"type": "unlimited"},
        ),
    )
    event.status = EventStatus.PUBLISHED
    await session.flush()

    # Тариф
    tariff = Tariff(
        id=uuid4(),
        event_id=event.id,
        organization_id=org.id,
        name="Standard",
        price_kopecks=price,
        is_active=True,
    )
    session.add(tariff)
    await session.flush()

    # Бронь
    reservation = Reservation(
        id=uuid4(),
        organization_id=org.id,
        event_id=event.id,
        first_name="Иван",
        last_name="Петров",
        email="ivan@example.com",
        phone="+79001234567",
        items_subtotal_kopecks=price,
        total_kopecks=price,
        status=status,
        consent_privacy=True,
        consent_offer=True,
    )
    session.add(reservation)
    await session.flush()

    item = ReservationItem(
        id=uuid4(),
        reservation_id=reservation.id,
        tariff_id=tariff.id,
        quantity=1,
        price_kopecks=price,
        subtotal_kopecks=price,
    )
    session.add(item)
    await session.flush()

    return reservation, str(tariff.id)


# ---------------------------------------------------------------------------
# Тесты
# ---------------------------------------------------------------------------


class TestPaymentStatus:
    """GET /api/v1/public/payments/{id}/status"""

    async def test_status_for_pending_reservation(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
    ) -> None:
        """Бронь без платежа → status=pending, payment_id=null."""
        org, _ = await _create_org_and_user(async_session, slug=f"pay-org-{uuid4().hex[:6]}")
        reservation, _ = await _setup_reservation(async_session, org)

        resp = await client.get(
            f"/api/v1/public/payments/{reservation.id}/status",
            headers={"X-Tenant-Slug": org.slug},
        )

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "pending"
        assert data["payment_id"] is None
        assert data["amount_kopecks"] == reservation.total_kopecks


class TestOrganizerMarkPaid:
    """POST /api/v1/organizer/reservations/{id}/mark-paid"""

    async def test_mark_paid_issues_tickets(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
    ) -> None:
        """Организатор отмечает оплату → issued tickets."""
        slug = f"pay-org-{uuid4().hex[:6]}"
        org, email = await _create_org_and_user(async_session, slug=slug)
        reservation, _ = await _setup_reservation(async_session, org)
        token = await _get_token(client, email)

        resp = await client.post(
            f"/api/v1/organizer/reservations/{reservation.id}/mark-paid",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Tenant-Slug": org.slug,
            },
        )

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "paid"
        assert data["tickets_issued"] == 1

        # Проверяем бронь
        await async_session.refresh(reservation)
        assert reservation.status == ReservationStatus.PAID
        assert reservation.paid_at is not None

    async def test_mark_paid_wrong_org_returns_404(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
    ) -> None:
        """Нельзя отметить оплату для чужой брони."""
        org1, _ = await _create_org_and_user(async_session, slug=f"org-a-{uuid4().hex[:6]}")
        org2, email2 = await _create_org_and_user(async_session, slug=f"org-b-{uuid4().hex[:6]}")
        reservation, _ = await _setup_reservation(async_session, org1)
        token = await _get_token(client, email2)

        # Пользователь org2 пытается отметить оплату брони org1
        resp = await client.post(
            f"/api/v1/organizer/reservations/{reservation.id}/mark-paid",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Tenant-Slug": org2.slug,
            },
        )

        assert resp.status_code == 404, resp.text


class TestOrganizerComplimentary:
    """POST /api/v1/organizer/reservations/{id}/complimentary"""

    async def test_complimentary_issues_free_tickets(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
    ) -> None:
        """Бесплатные билеты: платёж 0 руб, статус paid."""
        slug = f"comp-org-{uuid4().hex[:6]}"
        org, email = await _create_org_and_user(async_session, slug=slug)
        reservation, _ = await _setup_reservation(async_session, org, price=0)
        token = await _get_token(client, email)

        resp = await client.post(
            f"/api/v1/organizer/reservations/{reservation.id}/complimentary",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Tenant-Slug": org.slug,
            },
        )

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "paid"
        assert data["tickets_issued"] == 1

        # Проверяем что билеты выпущены
        await async_session.refresh(reservation)
        assert reservation.status == ReservationStatus.PAID


class TestPaymentStatusAfterPayment:
    """Статус после mark-paid."""

    async def test_status_after_payment(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
    ) -> None:
        """После оплаты статус = paid."""
        slug = f"stat-org-{uuid4().hex[:6]}"
        org, email = await _create_org_and_user(async_session, slug=slug)
        reservation, _ = await _setup_reservation(async_session, org)
        token = await _get_token(client, email)

        # Оплачиваем
        await client.post(
            f"/api/v1/organizer/reservations/{reservation.id}/mark-paid",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Tenant-Slug": org.slug,
            },
        )

        # Проверяем статус
        resp = await client.get(
            f"/api/v1/public/payments/{reservation.id}/status",
            headers={"X-Tenant-Slug": org.slug},
        )

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "paid"
        assert data["payment_id"] is not None
