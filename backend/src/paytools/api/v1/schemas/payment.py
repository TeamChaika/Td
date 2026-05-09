"""Pydantic-схемы для платежей."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from paytools.db.models.enums import PaymentProviderType, PaymentStatus
from paytools.db.models.payment import Payment


# --------------------------------------------------------------------------- #
# Ответы
# --------------------------------------------------------------------------- #


class PaymentStatusResponse(BaseModel):
    """Статус платежа (для поллинга на странице оплаты)."""

    model_config = ConfigDict(from_attributes=True)

    payment_id: UUID | None = None
    reservation_id: UUID
    status: PaymentStatus
    amount_kopecks: int
    currency: str = "RUB"
    provider: PaymentProviderType | None = None
    qr_url: str | None = None
    qr_image_url: str | None = None
    expires_at: datetime | None = None
    paid_at: datetime | None = None


class PaymentProcessResponse(BaseModel):
    """Ответ на создание/получение платежа."""

    payment_id: UUID
    reservation_id: UUID
    status: PaymentStatus
    amount_kopecks: int
    currency: str = "RUB"
    qr_url: str | None = None
    qr_image_base64: str | None = None
    expires_at: datetime


class PaymentConfirmResponse(BaseModel):
    """Ответ на подтверждение платежа."""

    payment_id: UUID
    status: PaymentStatus
    reservation_id: UUID
    tickets_issued: int


# --------------------------------------------------------------------------- #
# Webhook
# --------------------------------------------------------------------------- #


class QRMWebhookRequest(BaseModel):
    """Вебхук от QRM о смене статуса платежа.

    Формат зависит от версии QRM API. Поддерживаем основные поля.
    """

    invoice_id: str | None = None
    external_id: str | None = None  # Наш payment.id
    status: str  # paid, cancelled, expired
    amount: float | None = None


# --------------------------------------------------------------------------- #
# Builder-функции
# --------------------------------------------------------------------------- #


def build_payment_status_response(
    payment: Payment | None,
    reservation_id: UUID,
    amount_kopecks: int,
) -> PaymentStatusResponse:
    """Собрать PaymentStatusResponse."""
    if payment is None:
        return PaymentStatusResponse(
            reservation_id=reservation_id,
            status=PaymentStatus.PENDING,
            amount_kopecks=amount_kopecks,
        )
    return PaymentStatusResponse(
        payment_id=payment.id,
        reservation_id=payment.reservation_id,
        status=payment.status,
        amount_kopecks=payment.amount_kopecks,
        currency=payment.currency,
        provider=payment.provider,
        qr_url=payment.qr_url,
        qr_image_url=payment.qr_image_url,
        expires_at=payment.expires_at,
        paid_at=payment.paid_at,
    )


def build_payment_process_response(
    payment_id: UUID,
    reservation_id: UUID,
    status: PaymentStatus,
    amount_kopecks: int,
    expires_at: datetime,
    qr_url: str | None = None,
    qr_image_base64: str | None = None,
) -> PaymentProcessResponse:
    """Собрать PaymentProcessResponse."""
    return PaymentProcessResponse(
        payment_id=payment_id,
        reservation_id=reservation_id,
        status=status,
        amount_kopecks=amount_kopecks,
        qr_url=qr_url,
        qr_image_base64=qr_image_base64,
        expires_at=expires_at,
    )
