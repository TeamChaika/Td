"""Сервисный слой платежей.

Отвечает за:
- Создание платежа через QRM (QR-код)
- Подтверждение платежа (webhook / polling)
- Ручное проведение (cash/terminal/complimentary) — организатор
- Экспирация неподтверждённых платежей
- Выпуск билетов при успешной оплате
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from paytools.core.config import get_settings
from paytools.db.models.enums import (
    PaymentProviderType,
    PaymentStatus,
    ReservationStatus,
)
from paytools.db.models.payment import Payment
from paytools.db.models.reservation import Reservation
from paytools.db.repositories.payment import PaymentRepository
from paytools.db.repositories.reservation import ReservationRepository
from paytools.domain.payments.errors import (
    PaymentAlreadyConfirmedError,
    PaymentExpiredError,
    PaymentNotFoundError,
    PaymentProviderError,
    ReservationNotPendingError,
)
from paytools.domain.tickets.service import TicketService
from paytools.integrations.qrmanager import QRMClient, QRMError

# Время жизни платежа (минуты)
PAYMENT_TTL_MINUTES = 15


@dataclass(slots=True, kw_only=True)
class CreatePaymentResult:
    """Результат создания платежа."""

    payment_id: UUID
    invoice_id: str
    qr_url: str
    qr_image_base64: str | None
    payment_url: str | None
    amount_kopecks: int
    expires_at: datetime


class PaymentService:
    """Доменный сервис платежей."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        payment_repo: PaymentRepository,
        reservation_repo: ReservationRepository,
        ticket_service: TicketService,
    ) -> None:
        self.session = session
        self.payment_repo = payment_repo
        self.reservation_repo = reservation_repo
        self.ticket_service = ticket_service

    async def create_or_get_payment(
        self,
        org_id: UUID,
        reservation_id: UUID,
        *,
        api_key: str,
        login: str,
        return_url: str | None = None,
    ) -> CreatePaymentResult:
        """Создать платёж через QRM или вернуть существующий.

        Если существующий pending — возвращаем его.
        Если существующий истёк — создаём новый.
        Если уже paid — PaymentAlreadyConfirmedError.
        """
        reservation = await self.reservation_repo.get_with_items(reservation_id)
        if reservation is None or reservation.organization_id != org_id:
            raise ReservationNotPendingError(
                details={"reservation_id": str(reservation_id)}
            )
        if reservation.status != ReservationStatus.PENDING_PAYMENT:
            raise ReservationNotPendingError(
                details={
                    "reservation_id": str(reservation_id),
                    "status": reservation.status.value,
                }
            )

        # Проверяем существующий платёж
        existing = await self.payment_repo.get_by_reservation(reservation_id)
        if existing is not None:
            if existing.status == PaymentStatus.PAID:
                raise PaymentAlreadyConfirmedError(
                    details={"payment_id": str(existing.id)}
                )
            if existing.status == PaymentStatus.PENDING:
                now = datetime.now(UTC)
                if existing.expires_at and existing.expires_at > now:
                    # Возвращаем существующий pending
                    return CreatePaymentResult(
                        payment_id=existing.id,
                        invoice_id=existing.provider_payment_id or "",
                        qr_url=existing.qr_url or "",
                        qr_image_base64=existing.qr_image_url,
                        payment_url=None,
                        amount_kopecks=existing.amount_kopecks,
                        expires_at=existing.expires_at,
                    )
                # Истёк — отменяем и создаём новый
                existing.status = PaymentStatus.EXPIRED
                await self.session.flush()

        # Создаём новый платёж через QRM
        now = datetime.now(UTC)
        expires_at = now + timedelta(minutes=PAYMENT_TTL_MINUTES)

        # Сначала создаём запись в БД (нужен ID для invoice_id)
        payment = await self.payment_repo.create(
            organization_id=org_id,
            reservation_id=reservation_id,
            provider=PaymentProviderType.QRMANAGER,
            amount_kopecks=reservation.total_kopecks,
            currency="RUB",
            status=PaymentStatus.PENDING,
            expires_at=expires_at,
        )

        # Создаём счёт в QRM
        settings = get_settings()
        callback_url = f"{settings.platform_url}/api/v1/webhooks/qrm"
        qrm = QRMClient(base_url=settings.qrm_base_url)

        try:
            invoice = await qrm.create_invoice(
                amount_kopecks=reservation.total_kopecks,
                description=f"Билеты — {reservation.first_name} {reservation.last_name}",
                invoice_id=str(payment.id),
                callback_url=callback_url,
                api_key=api_key,
                login=login,
                email=reservation.email,
                phone=reservation.phone,
            )
        except QRMError as e:
            # Откатываем платёж в БД
            payment.status = PaymentStatus.CANCELLED
            await self.session.flush()
            raise PaymentProviderError(
                details={"error": str(e), "provider": "qrmanager"}
            ) from e

        # Обновляем платёж данными из QRM
        payment.provider_payment_id = invoice.invoice_id
        payment.qr_url = invoice.qr_url
        payment.qr_image_url = invoice.qr_image_base64
        await self.session.flush()

        return CreatePaymentResult(
            payment_id=payment.id,
            invoice_id=invoice.invoice_id,
            qr_url=invoice.qr_url,
            qr_image_base64=invoice.qr_image_base64,
            payment_url=invoice.payment_url,
            amount_kopecks=payment.amount_kopecks,
            expires_at=expires_at,
        )

    async def confirm_payment(
        self,
        provider_payment_id: str,
        *,
        provider_payload: dict | None = None,
    ) -> Payment:
        """Подтвердить платёж (вызывается из webhook или после проверки статуса).

        1. Находит платёж по provider_payment_id
        2. Обновляет статус на PAID
        3. Обновляет бронирование на PAID
        4. Выпускает билеты
        """
        payment = await self.payment_repo.get_by_provider_payment_id(
            provider_payment_id
        )
        if payment is None:
            raise PaymentNotFoundError(
                details={"provider_payment_id": provider_payment_id}
            )

        if payment.status == PaymentStatus.PAID:
            return payment  # Идемпотентно

        if payment.status not in (PaymentStatus.PENDING,):
            raise PaymentAlreadyConfirmedError(
                details={"payment_id": str(payment.id), "status": payment.status.value}
            )

        now = datetime.now(UTC)

        # Сохраняем webhook payload
        if provider_payload:
            events = payment.webhook_events or []
            events.append(provider_payload)
            payment.webhook_events = events

        payment.status = PaymentStatus.PAID
        payment.paid_at = now

        # Обновляем бронирование
        reservation = await self.reservation_repo.get(payment.reservation_id)
        if reservation is not None:
            reservation.status = ReservationStatus.PAID
            reservation.paid_at = now

        await self.session.flush()

        # Выпускаем билеты
        if reservation is not None:
            await self.ticket_service.issue_for_reservation(
                reservation.organization_id,
                payment.reservation_id,
            )

        return payment

    async def confirm_payment_by_reservation(
        self,
        org_id: UUID,
        reservation_id: UUID,
    ) -> Payment:
        """Оплата в обход QRM: cash / terminal (вызывается организатором)."""
        reservation = await self.reservation_repo.get_with_items(reservation_id)
        if reservation is None or reservation.organization_id != org_id:
            raise ReservationNotPendingError(
                details={"reservation_id": str(reservation_id)}
            )
        if reservation.status != ReservationStatus.PENDING_PAYMENT:
            raise ReservationNotPendingError(
                details={
                    "reservation_id": str(reservation_id),
                    "status": reservation.status.value,
                }
            )

        now = datetime.now(UTC)

        payment = await self.payment_repo.create(
            organization_id=org_id,
            reservation_id=reservation_id,
            provider=PaymentProviderType.CASH,
            amount_kopecks=reservation.total_kopecks,
            currency="RUB",
            status=PaymentStatus.PAID,
            paid_at=now,
        )

        reservation.status = ReservationStatus.PAID
        reservation.paid_at = now

        await self.session.flush()

        # Выпускаем билеты
        await self.ticket_service.issue_for_reservation(
            org_id, reservation_id
        )

        return payment

    async def create_complimentary_payment(
        self,
        org_id: UUID,
        reservation_id: UUID,
    ) -> Payment:
        """Бесплатные билеты (complimentary): платёж 0 руб, статус paid."""
        reservation = await self.reservation_repo.get_with_items(reservation_id)
        if reservation is None or reservation.organization_id != org_id:
            raise ReservationNotPendingError(
                details={"reservation_id": str(reservation_id)}
            )
        if reservation.status not in (
            ReservationStatus.PENDING_PAYMENT,
            ReservationStatus.DRAFT,
        ):
            raise ReservationNotPendingError(
                details={
                    "reservation_id": str(reservation_id),
                    "status": reservation.status.value,
                }
            )

        now = datetime.now(UTC)

        payment = await self.payment_repo.create(
            organization_id=org_id,
            reservation_id=reservation_id,
            provider=PaymentProviderType.COMPLIMENTARY,
            amount_kopecks=0,
            currency="RUB",
            status=PaymentStatus.PAID,
            paid_at=now,
        )

        reservation.status = ReservationStatus.PAID
        reservation.paid_at = now

        await self.session.flush()

        # Выпускаем билеты
        await self.ticket_service.issue_for_reservation(
            org_id, reservation_id
        )

        return payment

    async def get_payment_status(
        self, reservation_id: UUID
    ) -> Payment | None:
        """Получить статус платежа по бронированию."""
        return await self.payment_repo.get_by_reservation(reservation_id)

    async def expire_pending_payments(self) -> int:
        """Истечь все просроченные pending платежи.

        Вызывается arq cron-задачей раз в минуту.
        Возвращает количество обработанных платежей.
        """
        now = datetime.now(UTC)
        expired = await self.payment_repo.find_expired_pending(now)

        count = 0
        for payment in expired:
            payment.status = PaymentStatus.EXPIRED

            # Отменяем бронирование
            reservation = await self.reservation_repo.get(payment.reservation_id)
            if reservation and reservation.status == ReservationStatus.PENDING_PAYMENT:
                reservation.status = ReservationStatus.CANCELLED
                reservation.cancelled_at = now
                reservation.cancel_reason = "payment_expired"

            count += 1

        if count > 0:
            await self.session.flush()

        return count
