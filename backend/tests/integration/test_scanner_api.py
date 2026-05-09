"""Integration-тесты scanner check-in API (Phase 7)."""

from __future__ import annotations

from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from paytools.db.models.enums import (
    EventStatus,
    OrganizationStatus,
    ReservationStatus,
    UserRole,
)
from paytools.db.models.event import Event, Tariff
from paytools.db.models.organization import Organization
from paytools.db.models.reservation import Reservation, ReservationItem
from paytools.db.repositories.reservation import ReservationRepository
from paytools.db.repositories.ticket import TicketRepository
from paytools.db.repositories.user import UserRepository
from paytools.domain.tickets.service import TicketService
from paytools.core.security import hash_password


async def _setup(
    session: AsyncSession,
) -> tuple[Organization, str, str]:
    """Создать организацию со сканером, событие, бронь и билеты.
    Возвращает (org, scanner_email, ticket_code).
    """
    org = Organization(
        id=uuid4(),
        slug=f"scan-org-{uuid4().hex[:6]}",
        name="Scanner Test Org",
        status=OrganizationStatus.ACTIVE,
    )
    session.add(org)
    await session.flush()

    user_repo = UserRepository(session)
    scanner_email = f"scanner+{uuid4().hex[:4]}@example.com"
    await user_repo.create(
        email=scanner_email,
        password_hash=hash_password("Pass1234!"),
        first_name="Scan",
        last_name="User",
        role=UserRole.SCANNER,
        is_active=True,
        organization_id=org.id,
    )

    event = Event(
        id=uuid4(),
        organization_id=org.id,
        slug=f"scan-event-{uuid4().hex[:8]}",
        title="Scanner Test Event",
        schedule={
            "type": "single",
            "starts_at": "2027-06-01T20:00:00+03:00",
            "ends_at": "2027-06-01T23:00:00+03:00",
        },
        capacity_policy={"type": "unlimited"},
        status=EventStatus.PUBLISHED,
    )
    session.add(event)
    await session.flush()

    tariff = Tariff(
        id=uuid4(),
        event_id=event.id,
        organization_id=org.id,
        name="Standard",
        price_kopecks=100_00,
        is_active=True,
    )
    session.add(tariff)
    await session.flush()

    reservation = Reservation(
        id=uuid4(),
        organization_id=org.id,
        event_id=event.id,
        first_name="Иван",
        last_name="Петров",
        email="ivan@example.com",
        phone="+79001234567",
        items_subtotal_kopecks=100_00,
        total_kopecks=100_00,
        status=ReservationStatus.PAID,
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
        price_kopecks=100_00,
        subtotal_kopecks=100_00,
    )
    session.add(item)
    await session.flush()

    svc = TicketService(
        session,
        ticket_repo=TicketRepository(session),
        reservation_repo=ReservationRepository(session),
    )
    tickets = await svc.issue_for_reservation(org.id, reservation.id)
    ticket_code = tickets[0].code

    return org, scanner_email, ticket_code


async def _get_token(client: AsyncClient, email: str, slug: str) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Pass1234!"},
        headers={"X-Tenant-Slug": slug},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


class TestScannerCheckIn:
    """POST /api/v1/scanner/check-in"""

    async def test_check_in_by_code(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
    ) -> None:
        """Чек-ин по коду билета."""
        org, scanner_email, ticket_code = await _setup(async_session)
        token = await _get_token(client, scanner_email, org.slug)

        resp = await client.post(
            "/api/v1/scanner/check-in",
            json={"code": ticket_code},
            headers={
                "Authorization": f"Bearer {token}",
                "X-Tenant-Slug": org.slug,
            },
        )

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["ok"] is True
        assert data["code"] == ticket_code
        assert "Иван" in data["guest_name"]

    async def test_double_check_in_returns_error(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
    ) -> None:
        """Повторный чек-ин → ok=false."""
        org, scanner_email, ticket_code = await _setup(async_session)
        token = await _get_token(client, scanner_email, org.slug)

        # Первый чек-ин
        r1 = await client.post(
            "/api/v1/scanner/check-in",
            json={"code": ticket_code},
            headers={
                "Authorization": f"Bearer {token}",
                "X-Tenant-Slug": org.slug,
            },
        )
        assert r1.status_code == 200
        assert r1.json()["ok"] is True

        # Второй
        r2 = await client.post(
            "/api/v1/scanner/check-in",
            json={"code": ticket_code},
            headers={
                "Authorization": f"Bearer {token}",
                "X-Tenant-Slug": org.slug,
            },
        )
        assert r2.status_code == 200
        assert r2.json()["ok"] is False
        assert "уже использован" in r2.json()["error"]

    async def test_nonexistent_code(
        self,
        client: AsyncClient,
        async_session: AsyncSession,
    ) -> None:
        """Несуществующий код → ok=false."""
        org, scanner_email, _ = await _setup(async_session)
        token = await _get_token(client, scanner_email, org.slug)

        resp = await client.post(
            "/api/v1/scanner/check-in",
            json={"code": "XXXX-XXXX"},
            headers={
                "Authorization": f"Bearer {token}",
                "X-Tenant-Slug": org.slug,
            },
        )

        assert resp.status_code == 200
        assert resp.json()["ok"] is False
