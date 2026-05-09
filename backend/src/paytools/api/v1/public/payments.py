"""Публичные эндпоинты: оплата бронирования.

GET  /public/payments/{reservation_id}/status  — статус платежа (поллинг)
POST /public/payments/{reservation_id}/process — создать/получить QRM-платёж
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from paytools.api.v1.deps import SessionDep, TenantOrganization
from paytools.api.v1.schemas.payment import (
    PaymentProcessResponse,
    PaymentStatusResponse,
    build_payment_process_response,
    build_payment_status_response,
)
from paytools.core.config import get_settings
from paytools.core.errors import NotFoundError
from paytools.db.models.enums import PaymentStatus
from paytools.db.repositories.payment import PaymentRepository
from paytools.db.repositories.reservation import ReservationRepository
from paytools.db.repositories.ticket import TicketRepository
from paytools.domain.payments.service import PaymentService
from paytools.domain.tickets.service import TicketService

router = APIRouter()


def _build_payment_service(session: AsyncSession) -> PaymentService:
    """Собрать PaymentService с репозиториями."""
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


def _get_org_qrm_credentials(org_id: UUID) -> tuple[str, str]:
    """Получить QRM API key и login для организации.

    В MVP используем тестовый ключ из настроек.
    В production — из Organization.qrm_api_key_encrypted (расшифрованный).
    """
    settings = get_settings()
    api_key = settings.qrm_test_api_key or "test"
    login = "tdpay"
    return api_key, login


@router.get(
    "/payments/{reservation_id}/status",
    response_model=PaymentStatusResponse,
    summary="Статус платежа",
    description="Возвращает текущий статус платежа для поллинга на странице оплаты.",
)
async def get_payment_status(
    reservation_id: UUID,
    org: TenantOrganization,
    session: SessionDep,
) -> PaymentStatusResponse:
    """Статус платежа по бронированию."""
    svc = _build_payment_service(session)

    # Проверяем принадлежность бронирования
    reservation_repo = ReservationRepository(session)
    reservation = await reservation_repo.get(reservation_id)
    if reservation is None or reservation.organization_id != org.id:
        raise NotFoundError(
            "Бронирование не найдено",
            details={"reservation_id": str(reservation_id)},
        )

    payment = await svc.get_payment_status(reservation_id)
    return build_payment_status_response(
        payment,
        reservation_id=reservation_id,
        amount_kopecks=reservation.total_kopecks,
    )


@router.post(
    "/payments/{reservation_id}/process",
    response_model=PaymentProcessResponse,
    summary="Инициировать оплату",
    description="Создаёт платёж через QRM и возвращает QR-код. Идемпотентен.",
)
async def process_payment(
    reservation_id: UUID,
    org: TenantOrganization,
    session: SessionDep,
) -> PaymentProcessResponse:
    """Создать или получить QRM-платёж."""
    svc = _build_payment_service(session)

    # Проверяем принадлежность
    reservation_repo = ReservationRepository(session)
    reservation = await reservation_repo.get(reservation_id)
    if reservation is None or reservation.organization_id != org.id:
        raise NotFoundError(
            "Бронирование не найдено",
            details={"reservation_id": str(reservation_id)},
        )

    api_key, login = _get_org_qrm_credentials(org.id)

    result = await svc.create_or_get_payment(
        org_id=org.id,
        reservation_id=reservation_id,
        api_key=api_key,
        login=login,
    )

    return build_payment_process_response(
        payment_id=result.payment_id,
        reservation_id=reservation_id,
        status=PaymentStatus.PENDING,
        amount_kopecks=result.amount_kopecks,
        expires_at=result.expires_at,
        qr_url=result.qr_url,
        qr_image_base64=result.qr_image_base64,
    )
