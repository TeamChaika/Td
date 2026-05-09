"""Доменный модуль управления тарифами."""

from paytools.domain.tariffs.errors import (
    EventNotEditableForTariffError,
    TariffDeleteBlockedError,
    TariffNotFoundError,
    TariffPriceLockedError,
)
from paytools.domain.tariffs.service import (
    CreateTariffInput,
    TariffService,
    UpdateTariffInput,
)

__all__ = [
    "CreateTariffInput",
    "EventNotEditableForTariffError",
    "TariffDeleteBlockedError",
    "TariffNotFoundError",
    "TariffPriceLockedError",
    "TariffService",
    "UpdateTariffInput",
]
