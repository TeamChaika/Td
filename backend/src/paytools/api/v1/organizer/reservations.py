"""Эндпоинты организатора: управление бронированиями.

GET  /organizer/reservations          — список бронирований
GET  /organizer/reservations/{id}     — детали бронирования
POST /organizer/reservations/{id}/cancel — отменить бронирование
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy.ext.asyncio import AsyncSession

from paytools.api.v1.deps import CurrentOrganization, OrganizerUser, SessionDep
from paytools.api.v1.schemas.common import PaginatedResponse, Pagination
from paytools.api.v1.schemas.reservation import (
    CancelReservationRequest,
    ReservationListItem,
    ReservationResponse,
    build_reservation_list_item,
    build_reservation_response,
)
from paytools.core.errors import NotFoundError
from paytools.db.models.enums import ReservationStatus
from paytools.db.repositories.email_blocklist import EmailBlocklistRepository
from paytools.db.repositories.event import EventRepository
from paytools.db.repositories.promocode import (
    PromoCodeRepository,
    PromoCodeUsageRepository,
)
from paytools.db.repositories.reservation import ReservationRepository
from paytools.domain.bookings.service import BookingService

router = APIRouter()


def _build_booking_service(session: AsyncSession) -> BookingService:
    """Собрать BookingService с репозиториями."""
    return BookingService(
        session,
        reservation_repo=ReservationRepository(session),
        event_repo=EventRepository(session),
        promo_repo=PromoCodeRepository(session),
        usage_repo=PromoCodeUsageRepository(session),
        blocklist_repo=EmailBlocklistRepository(session),
    )


@router.get(
    "",
    response_model=PaginatedResponse[ReservationListItem],
    summary="Список бронирований организатора",
    description="Фильтры: event_id, status, from/to по дате. Пагинация.",
)
async def list_reservations(
    user: OrganizerUser,
    org: CurrentOrganization,
    session: SessionDep,
    event_id: Annotated[
        UUID | None, Query(description="Фильтр по событию")
    ] = None,
    status: Annotated[
        ReservationStatus | None, Query(description="Фильтр по статусу")
    ] = None,
    from_: Annotated[
        datetime | None, Query(alias="from", description="Бронирования с даты")
    ] = None,
    to: Annotated[
        datetime | None, Query(description="Бронирования до даты")
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedResponse[ReservationListItem]:
    """Список бронирований текущей организации с фильтрами."""
    svc = _build_booking_service(session)
    offset = (page - 1) * per_page

    items, total = await svc.list_for_organizer(
        org_id=org.id,
        event_id=event_id,
        status=status,
        from_date=from_,
        to_date=to,
        limit=per_page,
        offset=offset,
    )

    list_items = [build_reservation_list_item(r) for r in items]
    return PaginatedResponse[ReservationListItem](
        items=list_items,
        pagination=Pagination.build(page=page, per_page=per_page, total=total),
    )


@router.get(
    "/{reservation_id}",
    response_model=ReservationResponse,
    summary="Детали бронирования",
    description="Полная информация о бронировании, включая items.",
)
async def get_reservation(
    reservation_id: UUID,
    user: OrganizerUser,
    org: CurrentOrganization,
    session: SessionDep,
) -> ReservationResponse:
    """Получить детальную информацию о бронировании.

    Tenant isolation: проверка через organization_id.
    """
    svc = _build_booking_service(session)
    reservation = await svc.get(reservation_id)

    if reservation.organization_id != org.id:
        raise NotFoundError(
            "Бронирование не найдено",
            details={"reservation_id": str(reservation_id)},
        )

    return build_reservation_response(reservation)


@router.post(
    "/{reservation_id}/cancel",
    response_model=ReservationResponse,
    summary="Отменить бронирование",
    description="Отменяет бронирование с компенсацией capacity и промокода.",
)
async def cancel_reservation(
    reservation_id: UUID,
    data: CancelReservationRequest,
    user: OrganizerUser,
    org: CurrentOrganization,
    session: SessionDep,
) -> ReservationResponse:
    """Отменить бронирование.

    Tenant isolation: бронирование должно принадлежать current org, иначе 404.
    """
    svc = _build_booking_service(session)

    # Проверяем принадлежность
    reservation = await svc.get(reservation_id)
    if reservation.organization_id != org.id:
        raise NotFoundError(
            "Бронирование не найдено",
            details={"reservation_id": str(reservation_id)},
        )

    reservation = await svc.cancel(reservation_id, reason=data.reason)
    return build_reservation_response(reservation)
