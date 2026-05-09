"""Эндпоинты организатора: ручное проведение оплаты.

POST /organizer/reservations/{id}/mark-paid       — отметить как оплачено (cash/terminal)
POST /organizer/reservations/{id}/complimentary   — бесплатные билеты
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from paytools.api.v1.deps import CurrentOrganization, OrganizerUser, SessionDep
from paytools.api.v1.schemas.payment import PaymentConfirmResponse
from paytools.core.errors import NotFoundError
from paytools.db.repositories.payment import PaymentRepository
from paytools.db.repositories.reservation import ReservationRepository
from paytools.db.repositories.ticket import TicketRepository
from paytools.domain.payments.service import PaymentService
from paytools.domain.tickets.service import TicketService

router = APIRouter()


def _build_payment_service(session: AsyncSession) -> PaymentService:
    """Собрать PaymentService."""
    reservation_repo = ReservationRepository(session)
    return PaymentService(
        session,
        payment_repo=PaymentRepository(session),
        reservation_repo=reservation_repo,
        ticket_service=TicketService(
            session,
            ticket_repo=TicketRepository(session),
            reservation_repo=reservation_repo,
        ),
    )


@router.post(
    "/reservations/{reservation_id}/mark-paid",
    response_model=PaymentConfirmResponse,
    summary="Отметить оплату (cash/terminal)",
    description="Организатор подтверждает оплату наличными или терминалом.",
)
async def mark_paid(
    reservation_id: UUID,
    user: OrganizerUser,
    org: CurrentOrganization,
    session: SessionDep,
) -> PaymentConfirmResponse:
    """Ручное проведение оплаты."""
    svc = _build_payment_service(session)

    # Проверяем принадлежность
    reservation_repo = ReservationRepository(session)
    reservation = await reservation_repo.get(reservation_id)
    if reservation is None or reservation.organization_id != org.id:
        raise NotFoundError(
            "Бронирование не найдено",
            details={"reservation_id": str(reservation_id)},
        )

    payment = await svc.confirm_payment_by_reservation(
        org_id=org.id,
        reservation_id=reservation_id,
    )

    ticket_repo = TicketRepository(session)
    tickets_issued = await ticket_repo.count_for_reservation(reservation_id)

    return PaymentConfirmResponse(
        payment_id=payment.id,
        status=payment.status,
        reservation_id=reservation_id,
        tickets_issued=tickets_issued,
    )


@router.post(
    "/reservations/{reservation_id}/complimentary",
    response_model=PaymentConfirmResponse,
    summary="Бесплатные билеты",
    description="Выпустить бесплатные билеты (complimentary).",
)
async def mark_complimentary(
    reservation_id: UUID,
    user: OrganizerUser,
    org: CurrentOrganization,
    session: SessionDep,
) -> PaymentConfirmResponse:
    """Выпустить бесплатные билеты."""
    svc = _build_payment_service(session)

    reservation_repo = ReservationRepository(session)
    reservation = await reservation_repo.get(reservation_id)
    if reservation is None or reservation.organization_id != org.id:
        raise NotFoundError(
            "Бронирование не найдено",
            details={"reservation_id": str(reservation_id)},
        )

    payment = await svc.create_complimentary_payment(
        org_id=org.id,
        reservation_id=reservation_id,
    )

    ticket_repo = TicketRepository(session)
    tickets_issued = await ticket_repo.count_for_reservation(reservation_id)

    return PaymentConfirmResponse(
        payment_id=payment.id,
        status=payment.status,
        reservation_id=reservation_id,
        tickets_issued=tickets_issued,
    )
