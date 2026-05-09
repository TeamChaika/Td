"""Сканер: чек-ин билетов.

POST /scanner/check-in — проверить билет по коду или QR-пэйлоаду.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from paytools.api.v1.deps import (
    CurrentOrganization,
    ScannerUser,
    SessionDep,
)
from paytools.db.repositories.reservation import ReservationRepository
from paytools.db.repositories.ticket import TicketRepository
from paytools.domain.tickets.errors import (
    TicketAlreadyCheckedInError,
    TicketNotFoundError,
    TicketNotIssuedError,
)
from paytools.domain.tickets.service import TicketService

router = APIRouter()


class CheckInRequest(BaseModel):
    """Запрос на чек-ин."""

    code: str = Field(
        description="Код билета (XXXX-XXXX) или QR-пэйлоад"
    )


class CheckInResponse(BaseModel):
    """Ответ на чек-ин."""

    ok: bool
    ticket_id: str | None = None
    code: str | None = None
    guest_name: str | None = None
    guest_index: int | None = None
    status: str | None = None
    error: str | None = None


def _build_checkin_service(session: AsyncSession) -> TicketService:
    return TicketService(
        session,
        ticket_repo=TicketRepository(session),
        reservation_repo=ReservationRepository(session),
    )


@router.post(
    "/check-in",
    response_model=CheckInResponse,
    summary="Чек-ин билета",
    description="Сканер отправляет код билета или QR-пэйлоад для проверки.",
)
async def check_in(
    data: CheckInRequest,
    user: ScannerUser,
    org: CurrentOrganization,
    session: SessionDep,
) -> CheckInResponse:
    """Проверить билет и отметить вход."""
    svc = _build_checkin_service(session)

    try:
        ticket = await svc.check_in(data.code, user_id=user.id)
        return CheckInResponse(
            ok=True,
            ticket_id=str(ticket.id),
            code=ticket.code,
            guest_name=f"{ticket.guest_first_name} {ticket.guest_last_name}",
            guest_index=ticket.guest_index,
            status=ticket.status.value,
        )
    except TicketAlreadyCheckedInError:
        # Ищем билет чтобы вернуть инфо даже при повторном скане
        ticket_repo = TicketRepository(session)
        ticket = await ticket_repo.get_by_code(data.code)
        if ticket is None and "." in data.code:
            from paytools.domain.tickets.service import _verify_qr_payload
            payload = _verify_qr_payload(data.code)
            if payload and "ticket_id" in payload:
                from uuid import UUID
                ticket = await ticket_repo.get(UUID(payload["ticket_id"]))

        if ticket:
            return CheckInResponse(
                ok=False,
                ticket_id=str(ticket.id),
                code=ticket.code,
                guest_name=f"{ticket.guest_first_name} {ticket.guest_last_name}",
                guest_index=ticket.guest_index,
                status=ticket.status.value,
                error="Билет уже использован для входа",
            )
        return CheckInResponse(ok=False, error="Билет уже использован")

    except TicketNotFoundError:
        return CheckInResponse(ok=False, error="Билет не найден")

    except TicketNotIssuedError:
        return CheckInResponse(ok=False, error="Билет не действителен")
