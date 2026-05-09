"""Доменные ошибки для модуля tariffs."""

from __future__ import annotations

from paytools.core.errors import ConflictError, NotFoundError


class TariffNotFoundError(NotFoundError):
    """Тариф не найден."""

    code = "tariff_not_found"
    default_message = "Тариф не найден"


class TariffPriceLockedError(ConflictError):
    """Нельзя изменить цену тарифа — есть проданные билеты."""

    code = "tariff_price_locked"
    default_message = (
        "Нельзя изменить цену тарифа: уже есть проданные билеты. Создайте новый тариф."
    )


class TariffDeleteBlockedError(ConflictError):
    """Нельзя удалить тариф жёстко — есть проданные билеты."""

    code = "tariff_delete_blocked"
    default_message = "Тариф деактивирован (есть проданные билеты)"


class EventNotEditableForTariffError(ConflictError):
    """Событие в статусе, не допускающем изменение тарифов."""

    code = "event_not_editable_for_tariff"
    default_message = (
        "Тарифы можно менять только у событий в статусе draft или published"
    )
