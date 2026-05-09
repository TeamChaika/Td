"""Доменные ошибки для модуля промокодов."""

from __future__ import annotations

from paytools.core.errors import ConflictError, NotFoundError, ValidationError


class PromoCodeNotFoundError(NotFoundError):
    """Промокод не найден."""

    code = "promo_code_not_found"
    default_message = "Промокод не найден"


class PromoCodeInactiveError(ValidationError):
    """Промокод деактивирован."""

    code = "promo_code_inactive"
    default_message = "Промокод неактивен"


class PromoCodeExpiredError(ValidationError):
    """Промокод истёк (вне active_from/active_to)."""

    code = "promo_code_expired"
    default_message = "Промокод истёк или ещё не начал действовать"


class PromoCodeUsageLimitError(ValidationError):
    """Промокод исчерпал лимит использований."""

    code = "promo_code_usage_limit"
    default_message = "Промокод исчерпал лимит использований"


class PromoCodePerUserLimitError(ValidationError):
    """Пользователь исчерпал лимит по промокоду."""

    code = "promo_code_per_user_limit"
    default_message = "Вы уже использовали этот промокод максимальное количество раз"


class PromoCodeWrongEventError(ValidationError):
    """Промокод не действует на это событие."""

    code = "promo_code_wrong_event"
    default_message = "Промокод не действует для этого события"


class PromoCodeWrongTariffError(ValidationError):
    """Промокод не действует на этот тариф."""

    code = "promo_code_wrong_tariff"
    default_message = "Промокод не действует для этого тарифа"


class PromoCodeHasUsagesError(ConflictError):
    """Нельзя удалить промокод с историей использований."""

    code = "promo_code_has_usages"
    default_message = "Нельзя удалить промокод, который уже использовался"


class PromoCodeDuplicateError(ConflictError):
    """Промокод с таким кодом уже существует."""

    code = "promo_code_duplicate"
    default_message = "Промокод с таким кодом уже существует"
