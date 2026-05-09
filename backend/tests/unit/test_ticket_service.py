"""Unit-тесты TicketService: выпуск билетов, check-in, QR-подпись."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from paytools.db.models.enums import (
    EventStatus,
    OrganizationStatus,
    ReservationStatus,
    TicketStatus,
)
from paytools.db.models.event import Event, Tariff
from paytools.db.models.organization import Organization
from paytools.db.models.reservation import Reservation, ReservationItem
from paytools.db.repositories.reservation import ReservationRepository
from paytools.db.repositories.ticket import TicketRepository
from paytools.domain.tickets.errors import (
    TicketAlreadyCheckedInError,
    TicketNotFoundError,
    TicketNotIssuedError,
)
from paytools.domain.tickets.service import (
    TicketService,
    _generate_ticket_code,
    _verify_qr_payload,
)


# ---------------------------------------------------------------------------
# Хелперы
# ---------------------------------------------------------------------------


def _make_org() -> Organization:
    return Organization(
        id=uuid4(),
        slug=f"tickets-org-{uuid4().hex[:8]}",
        name="Ticket Test Org",
        status=OrganizationStatus.ACTIVE,
    )


def _make_event(org: Organization) -> Event:
    return Event(
        id=uuid4(),
        organization_id=org.id,
        slug=f"ticket-event-{uuid4().hex[:8]}",
        title="Ticket Test Event",
        schedule={
            "type": "single",
            "starts_at": "2027-01-01T20:00:00+03:00",
            "ends_at": "2027-01-01T23:00:00+03:00",
        },
        capacity_policy={"type": "unlimited"},
        status=EventStatus.PUBLISHED,
    )


def _make_tariff(event: Event, org: Organization, price: int = 100000) -> Tariff:
    return Tariff(
        id=uuid4(),
        event_id=event.id,
        organization_id=org.id,
        name="Standard",
        price_kopecks=price,
        is_active=True,
    )


def _make_reservation(
    org: Organization, event: Event, tariff: Tariff, quantity: int = 1
) -> Reservation:
    r = Reservation(
        id=uuid4(),
        organization_id=org.id,
        event_id=event.id,
        first_name="Иван",
        last_name="Петров",
        email="ivan@example.com",
        phone="+79001234567",
        items_subtotal_kopecks=tariff.price_kopecks * quantity,
        total_kopecks=tariff.price_kopecks * quantity,
        status=ReservationStatus.PAID,
        consent_privacy=True,
        consent_offer=True,
    )
    item = ReservationItem(
        id=uuid4(),
        reservation_id=r.id,
        tariff_id=tariff.id,
        quantity=quantity,
        price_kopecks=tariff.price_kopecks,
        subtotal_kopecks=tariff.price_kopecks * quantity,
    )
    r.items = [item]
    return r


async def _persist(session: AsyncSession, *objects: object) -> None:
    """Добавить объекты в правильном порядке с flush после каждого."""
    for obj in objects:
        session.add(obj)
        await session.flush()


def _svc(session: AsyncSession) -> TicketService:
    return TicketService(
        session,
        ticket_repo=TicketRepository(session),
        reservation_repo=ReservationRepository(session),
    )


# ---------------------------------------------------------------------------
# Тесты: QR-пэйлоад
# ---------------------------------------------------------------------------


class TestQRPayload:
    """Тесты генерации и верификации QR-пэйлоада."""

    async def test_build_and_verify(
        self, async_session: AsyncSession
    ) -> None:
        """Подписанный пэйлоад проходит верификацию."""
        org = _make_org()
        event = _make_event(org)
        tariff = _make_tariff(event, org)
        reservation = _make_reservation(org, event, tariff, quantity=2)

        await _persist(async_session, org, event, tariff, reservation)

        svc = _svc(async_session)
        tickets = await svc.issue_for_reservation(org.id, reservation.id)

        assert len(tickets) == 2

        for ticket in tickets:
            payload = _verify_qr_payload(ticket.qr_payload)
            assert payload is not None, f"QR payload must verify: {ticket.code}"
            assert payload["ticket_id"] == str(ticket.id)
            assert payload["event_id"] == str(event.id)
            assert payload["code"] == ticket.code

    def test_tampered_payload_fails_verification(self) -> None:
        """Модифицированный пэйлоад не проходит проверку."""
        assert _verify_qr_payload("bad.data") is None
        assert _verify_qr_payload("invalid") is None
        assert _verify_qr_payload("") is None


# ---------------------------------------------------------------------------
# Тесты: генерация кодов
# ---------------------------------------------------------------------------


class TestTicketCode:
    """Тесты генерации кодов билетов."""

    def test_format(self) -> None:
        """Код имеет формат XXXX-XXXX."""
        for _ in range(50):
            code = _generate_ticket_code()
            parts = code.split("-")
            assert len(parts) == 2, f"Expected XXXX-XXXX, got {code}"
            assert len(parts[0]) == 4
            assert len(parts[1]) == 4
            for part in parts:
                for ch in part:
                    assert ch not in "0O1IL", f"Confusing char in {code}"


# ---------------------------------------------------------------------------
# Тесты: выпуск билетов
# ---------------------------------------------------------------------------


class TestTicketIssuance:
    """Тесты выпуска билетов."""

    async def test_issue_single_ticket(
        self, async_session: AsyncSession
    ) -> None:
        """Выпуск одного билета."""
        org = _make_org()
        event = _make_event(org)
        tariff = _make_tariff(event, org)
        reservation = _make_reservation(org, event, tariff)

        await _persist(async_session, org, event, tariff, reservation)

        svc = _svc(async_session)
        tickets = await svc.issue_for_reservation(org.id, reservation.id)

        assert len(tickets) == 1
        ticket = tickets[0]
        assert ticket.event_id == event.id
        assert ticket.reservation_id == reservation.id
        assert ticket.status == TicketStatus.ISSUED
        assert ticket.guest_index == 0
        assert ticket.code is not None
        assert len(ticket.code) == 9
        assert ticket.qr_payload is not None

    async def test_issue_multiple_tickets(
        self, async_session: AsyncSession
    ) -> None:
        """Выпуск нескольких билетов (quantity=3)."""
        org = _make_org()
        event = _make_event(org)
        tariff = _make_tariff(event, org)
        reservation = _make_reservation(org, event, tariff, quantity=3)

        await _persist(async_session, org, event, tariff, reservation)

        svc = _svc(async_session)
        tickets = await svc.issue_for_reservation(org.id, reservation.id)

        assert len(tickets) == 3
        for i, ticket in enumerate(tickets):
            assert ticket.guest_index == i
            assert ticket.code is not None
            assert ticket.qr_payload is not None

    async def test_idempotent_issue(
        self, async_session: AsyncSession
    ) -> None:
        """Повторный выпуск возвращает существующие билеты."""
        org = _make_org()
        event = _make_event(org)
        tariff = _make_tariff(event, org)
        reservation = _make_reservation(org, event, tariff)

        await _persist(async_session, org, event, tariff, reservation)

        svc = _svc(async_session)
        tickets1 = await svc.issue_for_reservation(org.id, reservation.id)
        tickets2 = await svc.issue_for_reservation(org.id, reservation.id)

        assert len(tickets1) == 1
        assert len(tickets2) == 1
        assert tickets1[0].id == tickets2[0].id

    async def test_issue_for_nonexistent_reservation(
        self, async_session: AsyncSession
    ) -> None:
        """Выпуск для несуществующей брони вызывает ошибку."""
        svc = _svc(async_session)
        with pytest.raises(TicketNotIssuedError):
            await svc.issue_for_reservation(uuid4(), uuid4())


# ---------------------------------------------------------------------------
# Тесты: check-in
# ---------------------------------------------------------------------------


class TestTicketCheckIn:
    """Тесты чек-ина билетов."""

    async def test_check_in_by_code(
        self, async_session: AsyncSession
    ) -> None:
        """Чек-ин по человекочитаемому коду."""
        org = _make_org()
        event = _make_event(org)
        tariff = _make_tariff(event, org)
        reservation = _make_reservation(org, event, tariff)

        await _persist(async_session, org, event, tariff, reservation)

        svc = _svc(async_session)
        tickets = await svc.issue_for_reservation(org.id, reservation.id)
        code = tickets[0].code

        checked_in = await svc.check_in(code)
        assert checked_in.status == TicketStatus.CHECKED_IN
        assert checked_in.checked_in_at is not None

    async def test_check_in_by_qr_payload(
        self, async_session: AsyncSession
    ) -> None:
        """Чек-ин по QR-пэйлоаду."""
        org = _make_org()
        event = _make_event(org)
        tariff = _make_tariff(event, org)
        reservation = _make_reservation(org, event, tariff)

        await _persist(async_session, org, event, tariff, reservation)

        svc = _svc(async_session)
        tickets = await svc.issue_for_reservation(org.id, reservation.id)
        qr = tickets[0].qr_payload

        checked_in = await svc.check_in(qr)
        assert checked_in.status == TicketStatus.CHECKED_IN

    async def test_double_check_in_raises(
        self, async_session: AsyncSession
    ) -> None:
        """Повторный чек-ин вызывает ошибку."""
        org = _make_org()
        event = _make_event(org)
        tariff = _make_tariff(event, org)
        reservation = _make_reservation(org, event, tariff)

        await _persist(async_session, org, event, tariff, reservation)

        svc = _svc(async_session)
        tickets = await svc.issue_for_reservation(org.id, reservation.id)
        code = tickets[0].code

        await svc.check_in(code)
        with pytest.raises(TicketAlreadyCheckedInError):
            await svc.check_in(code)

    async def test_check_in_nonexistent_code_raises(
        self, async_session: AsyncSession
    ) -> None:
        """Чек-ин по несуществующему коду вызывает ошибку."""
        svc = _svc(async_session)
        with pytest.raises(TicketNotFoundError):
            await svc.check_in("XXXX-XXXX")
