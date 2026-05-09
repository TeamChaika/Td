"""Доменные ошибки модуля аутентификации."""

from __future__ import annotations

from paytools.core.errors import AuthError, ForbiddenError, ValidationError


class InvalidCredentialsError(AuthError):
    """Неверный email или пароль (возвращаем общее сообщение, не палим подробности)."""

    code = "invalid_credentials"
    default_message = "Неверный email или пароль"


class InvalidRefreshTokenError(AuthError):
    """Refresh-токен невалиден, истёк или отозван."""

    code = "invalid_refresh_token"
    default_message = "Refresh-токен недействителен"


class PasswordTooWeakError(ValidationError):
    """Пароль не соответствует policy (min 10 символов)."""

    code = "password_too_weak"
    default_message = "Пароль должен содержать минимум 10 символов"


class SlugInvalidError(ValidationError):
    """Slug не прошёл валидацию (too_short/too_long/invalid_format/reserved)."""

    code = "slug_invalid"
    default_message = "Некорректный slug"


class InvalidMagicLinkError(AuthError):
    """Magic-link токен невалиден, истёк или уже использован."""

    code = "invalid_magic_link"
    default_message = "Ссылка для входа недействительна или истекла"


class EmailBlockedError(ValidationError):
    """Регистрация/вход с этого email запрещены (email в блоклисте)."""

    code = "email_blocked"
    default_message = "Регистрация с этого email запрещена"


class OrganizationPendingError(ForbiddenError):
    """Организация ещё не прошла модерацию (PENDING_MODERATION)."""

    code = "organization_pending"
    default_message = "Организация ожидает модерации"
