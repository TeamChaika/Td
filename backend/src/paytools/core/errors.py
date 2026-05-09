"""Доменные ошибки и маппинг на HTTP-ответы.

Все доменные сервисы должны кидать наследников `DomainError`.
Middleware/exception_handler преобразуют их в единый JSON-формат.
"""

from __future__ import annotations

from typing import Any, ClassVar


class DomainError(Exception):
    """Базовая доменная ошибка. Наследники задают code/status_code."""

    code: ClassVar[str] = "domain_error"
    status_code: ClassVar[int] = 400
    default_message: ClassVar[str] = "Доменная ошибка"

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message: str = message or self.default_message
        self.details: dict[str, Any] | None = details
        super().__init__(self.message)


class ValidationError(DomainError):
    code = "validation_error"
    status_code = 400
    default_message = "Некорректные данные"


class NotFoundError(DomainError):
    code = "not_found"
    status_code = 404
    default_message = "Объект не найден"


class ConflictError(DomainError):
    code = "conflict"
    status_code = 409
    default_message = "Конфликт состояния"


class UnauthorizedError(DomainError):
    code = "unauthorized"
    status_code = 401
    default_message = "Требуется авторизация"


class ForbiddenError(DomainError):
    code = "forbidden"
    status_code = 403
    default_message = "Доступ запрещён"


class RateLimitError(DomainError):
    code = "rate_limited"
    status_code = 429
    default_message = "Слишком много запросов, попробуйте позже"


class PaymentError(DomainError):
    code = "payment_error"
    status_code = 502
    default_message = "Ошибка платёжного провайдера"


class AuthError(UnauthorizedError):
    """Невалидный / истёкший токен."""

    code = "invalid_token"
    default_message = "Токен недействителен"


class IdempotencyConflictError(ConflictError):
    """Запрос с тем же Idempotency-Key уже выполняется с другим телом."""

    code = "idempotency_conflict"
    default_message = (
        "Запрос с таким Idempotency-Key уже обрабатывается с другими параметрами"
    )


# ---------------------------------------------------------------------------
# Ошибки аутентификации / авторизации (были в api/v1/deps.py, перенесены
# в core/errors.py для доступности всем слоям без циклических импортов)
# ---------------------------------------------------------------------------


class TokenExpiredError(AuthError):
    """Токен истёк (ExpiredSignatureError)."""

    code = "token_expired"
    default_message = "Access token истёк"

    def __init__(self, message: str | None = None, **kwargs: Any) -> None:
        super().__init__(message=message or self.default_message, **kwargs)


class UserInactiveError(ForbiddenError):
    """Пользователь деактивирован (is_active=False)."""

    code = "user_inactive"
    default_message = "Пользователь деактивирован"

    def __init__(self, message: str | None = None, **kwargs: Any) -> None:
        super().__init__(message=message or self.default_message, **kwargs)


class OrganizationRequiredError(ForbiddenError):
    """Эндпоинт требует принадлежности к организации, а пользователь — без неё."""

    code = "organization_required"
    default_message = "Эндпоинт требует принадлежности к организации"

    def __init__(self, message: str | None = None, **kwargs: Any) -> None:
        super().__init__(message=message or self.default_message, **kwargs)


class OrganizationSuspendedError(ForbiddenError):
    """Организация заблокирована (SUSPENDED)."""

    code = "organization_suspended"
    default_message = "Организация заблокирована"

    def __init__(self, message: str | None = None, **kwargs: Any) -> None:
        super().__init__(message=message or self.default_message, **kwargs)


class InsufficientRoleError(ForbiddenError):
    """Роль пользователя недостаточна для доступа к эндпоинту."""

    code = "insufficient_role"
    default_message = "Недостаточно прав"

    def __init__(self, message: str | None = None, **kwargs: Any) -> None:
        super().__init__(message=message or self.default_message, **kwargs)


class TenantNotResolvedError(NotFoundError):
    """Арендатор не определён (нет subdomain / заголовка)."""

    code = "tenant_not_resolved"
    default_message = "Арендатор не определён"

    def __init__(self, message: str | None = None, **kwargs: Any) -> None:
        super().__init__(message=message or self.default_message, **kwargs)
