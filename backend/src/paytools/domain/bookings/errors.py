"""Доменные ошибки для модуля bookings."""

from __future__ import annotations

from paytools.core.errors import ConflictError, NotFoundError, ValidationError


class ReservationNotFoundError(NotFoundError):
    """Бронирование не найдено."""

    code = "reservation_not_found"
    default_message = "Бронирование не найдено"


class CapacityExceededError(ConflictError):
    """Нет доступных мест (sold out)."""

    code = "capacity_exceeded"
    default_message = "Нет доступных мест"


class EventNotPublishedError(ValidationError):
    """Событие не опубликовано — нельзя бронировать."""

    code = "event_not_published"
    default_message = "Событие не доступно для бронирования"


class TariffNotAvailableError(ValidationError):
    """Тариф неактивен или не принадлежит событию."""

    code = "tariff_not_available"
    default_message = "Тариф недоступен"


class EmailBlockedError(ValidationError):
    """Email из блоклиста (disposable)."""

    code = "email_blocked"
    default_message = "Данный email не принимается для бронирования"


class ConsentRequiredError(ValidationError):
    """Не предоставлено согласие на обработку ПДн / оферту."""

    code = "consent_required"
    default_message = "Необходимо согласие на обработку ПДн и оферту"


class ReservationExpiredError(ConflictError):
    """Бронирование истекло."""

    code = "reservation_expired"
    default_message = "Время бронирования истекло"


class ReservationAlreadyCancelledError(ConflictError):
    """Бронирование уже отменено."""

    code = "reservation_already_cancelled"
    default_message = "Бронирование уже отменено"
