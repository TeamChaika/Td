"""Доменные ошибки для модуля payments."""

from __future__ import annotations

from paytools.core.errors import ConflictError, NotFoundError, ValidationError


class PaymentNotFoundError(NotFoundError):
    """Платёж не найден."""

    code = "payment_not_found"
    default_message = "Платёж не найден"


class PaymentAlreadyConfirmedError(ConflictError):
    """Платёж уже подтверждён."""

    code = "payment_already_confirmed"
    default_message = "Платёж уже подтверждён"


class PaymentExpiredError(ConflictError):
    """Платёж истёк."""

    code = "payment_expired"
    default_message = "Время оплаты истекло"


class PaymentProviderError(ConflictError):
    """Ошибка платёжного провайдера."""

    code = "payment_provider_error"
    default_message = "Ошибка платёжного провайдера"


class ReservationNotPendingError(ConflictError):
    """Бронь не в статусе pending_payment — нельзя создать платёж."""

    code = "reservation_not_pending"
    default_message = "Бронь не ожидает оплаты"
