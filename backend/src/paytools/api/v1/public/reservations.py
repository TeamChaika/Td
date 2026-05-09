"""Публичные эндпоинты: создание бронирования и проверка статуса.

POST /public/reservations          — создать бронь
GET  /public/reservations/{id}     — получить бронь по id
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from paytools.api.v1.deps import SessionDep, TenantOrganization
from paytools.api.v1.schemas.reservation import (
    CreateReservationRequest,
    ReservationCreateResponse,
    ReservationResponse,
    build_reservation_create_response,
    build_reservation_response,
)
from paytools.core.errors import NotFoundError
from paytools.db.repositories.email_blocklist import EmailBlocklistRepository
from paytools.db.repositories.event import EventRepository
from paytools.db.repositories.promocode import (
    PromoCodeRepository,
    PromoCodeUsageRepository,
)
from paytools.db.repositories.reservation import ReservationRepository
from paytools.domain.bookings.service import (
    BookingService,
    CreateReservationInput,
    ReservationItemData,
)

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


@router.post(
    "/reservations",
    response_model=ReservationCreateResponse,
    status_code=201,
    summary="Создать бронирование",
    description=(
        "Создаёт бронирование со статусом pending_payment. "
        "Бронь живёт 15 минут, потом автоматически истекает."
    ),
)
async def create_reservation(
    data: CreateReservationRequest,
    org: TenantOrganization,
    session: SessionDep,
    request: Request,
    idempotency_key: str | None = Header(
        default=None, alias="Idempotency-Key"
    ),
) -> ReservationCreateResponse:
    """Создать бронирование.

    Tenant isolation: организация определяется из subdomain.
    """
    svc = _build_booking_service(session)

    # Извлекаем IP и User-Agent
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    reservation = await svc.create_reservation(
        org_id=org.id,
        data=CreateReservationInput(
            event_id=data.event_id,
            session_id=data.session_id,
            first_name=data.first_name,
            last_name=data.last_name,
            email=data.email,
            phone=data.phone,
            items=[
                ReservationItemData(
                    tariff_id=item.tariff_id,
                    quantity=item.quantity,
                )
                for item in data.items
            ],
            custom_fields=data.custom_fields,
            promo_code=data.promo_code,
            referrer_code=data.referrer_code,
            consent_privacy=data.consent_privacy,
            consent_offer=data.consent_offer,
            idempotency_key=idempotency_key,
            user_agent=user_agent,
            ip=ip,
        ),
    )

    return build_reservation_create_response(reservation)


@router.get(
    "/reservations/{reservation_id}",
    response_model=ReservationResponse,
    summary="Получить бронирование",
    description="Возвращает полную информацию о бронировании по ID.",
)
async def get_reservation(
    reservation_id: UUID,
    org: TenantOrganization,
    session: SessionDep,
) -> ReservationResponse:
    """Получить бронирование по ID.

    Tenant isolation: проверяем org через tenant subdomain.
    """
    svc = _build_booking_service(session)
    reservation = await svc.get(reservation_id)

    # Проверяем принадлежность к организации
    if reservation.organization_id != org.id:
        raise NotFoundError(
            "Бронирование не найдено",
            details={"reservation_id": str(reservation_id)},
        )

    return build_reservation_response(reservation)


@router.get(
    "/reservations/{reservation_id}/status",
    summary="Поллинг статуса бронирования",
    description="Возвращает текущий статус бронирования (для поллинга).",
)
async def get_reservation_status(
    reservation_id: UUID,
    org: TenantOrganization,
    session: SessionDep,
) -> dict[str, object]:
    """Статус бронирования (MVP-поллинг, в v1.1 — SSE)."""
    svc = _build_booking_service(session)
    reservation = await svc.get(reservation_id)

    if reservation.organization_id != org.id:
        raise NotFoundError(
            "Бронирование не найдено",
            details={"reservation_id": str(reservation_id)},
        )

    return {
        "status": reservation.status.value,
        "total_kopecks": reservation.total_kopecks,
        "expires_at": (
            reservation.expires_at.isoformat() if reservation.expires_at else None
        ),
    }
