"""FastAPI-зависимости: auth, tenant, ролевые guards.

Все зависимости async, с полной типизацией.
Используются во всех endpoint'ах API v1.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Annotated, Any
from uuid import UUID

import jwt
from fastapi import Depends, Header, Request
from pydantic import BaseModel, ValidationError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from paytools.core.db import get_session
from paytools.core.errors import (
    AuthError,
    InsufficientRoleError,
    NotFoundError,
    OrganizationRequiredError,
    OrganizationSuspendedError,
    TenantNotResolvedError,
    TokenExpiredError,
    UserInactiveError,
)
from paytools.core.redis import get_redis_client
from paytools.core.security import decode_token
from paytools.core.tenancy import current_organization_id
from paytools.db.models.enums import OrganizationStatus, UserRole
from paytools.db.models.organization import Organization
from paytools.db.models.user import User
from paytools.db.repositories.organization import OrganizationRepository
from paytools.db.repositories.user import UserRepository

# ---------------------------------------------------------------------------
# Типовой alias для сессии БД (используется в зависимостях ниже)
# ---------------------------------------------------------------------------

SessionDep = Annotated[AsyncSession, Depends(get_session)]

# ---------------------------------------------------------------------------
# Redis dependency
# ---------------------------------------------------------------------------

# types-redis объявляет Redis как generic, но runtime redis-py — нет.
# Для mypy используем Redis[str]; Annotated вычисляется в runtime, поэтому
# обходим через TYPE_CHECKING — в runtime получаем голый Redis, для mypy — Redis[str].
if TYPE_CHECKING:
    _RedisStr = Redis[str]
else:
    _RedisStr = Redis


async def get_redis() -> _RedisStr:
    """Dependency для Redis."""
    return get_redis_client()


RedisDep = Annotated[_RedisStr, Depends(get_redis)]

# Реэкспорт ошибок для совместимости — все импорты должны идти из core.errors
__all__ = [
    "CurrentOrganization",
    "CurrentUser",
    "InsufficientRoleError",
    "OrganizationRequiredError",
    "OrganizationSuspendedError",
    "OrganizerUser",
    "ScannerUser",
    "SessionDep",
    "SuperadminUser",
    "TenantNotResolvedError",
    "TenantOrganization",
    "TokenExpiredError",
    "TokenPayload",
    "UserInactiveError",
    "get_access_token",
    "get_current_organization",
    "get_current_user",
    "get_tenant_organization",
    "get_tenant_slug",
    "get_token_payload",
    "get_token_payload_optional",
    "require_organizer",
    "require_organizer_or_above",
    "require_roles",
    "require_superadmin",
]


# ---------------------------------------------------------------------------
# Pydantic-модель JWT payload
# ---------------------------------------------------------------------------

# Используем Pydantic вместо сырого dict[str, Any] потому что:
#  1. type-safety — mypy проверяет поля на этапе написания кода
#  2. авто-валидация — UUID парсится из строки, обязательные поля проверяются
#  3. самодокументирование — видна полная структура payload
#  4. консистентность — весь проект на Pydantic v2


class TokenPayload(BaseModel):
    """Валидированное содержимое JWT access/refresh-токена."""

    sub: UUID
    org: UUID | None = None
    role: str
    type: str  # "access" / "refresh" — проверяется в get_token_payload
    exp: int
    jti: str
    iat: int


# ---------------------------------------------------------------------------
# 1. Парсинг Bearer-токена
# ---------------------------------------------------------------------------


async def get_access_token(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> str:
    """Извлекает access-токен из заголовка Authorization: Bearer <token>."""
    if authorization is None:
        raise AuthError("Missing or malformed Authorization header")
    if not authorization.startswith("Bearer "):
        raise AuthError("Missing or malformed Authorization header")
    token = authorization[7:].strip()
    if not token:
        raise AuthError("Missing or malformed Authorization header")
    return token


# ---------------------------------------------------------------------------
# 2. Декодирование токена + проверка type=access
# ---------------------------------------------------------------------------


async def get_token_payload(
    token: Annotated[str, Depends(get_access_token)],
    redis: RedisDep,
) -> TokenPayload:
    """Декодирует JWT, валидирует claims и возвращает типизированный payload.

    Бросает TokenExpiredError / AuthError при любых проблемах с токеном.
    Также проверяет, не находится ли jti в блок-листе (ревокация при logout).
    """
    # Декодируем (может бросить jwt.InvalidTokenError)
    try:
        raw: dict[str, Any] = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError() from None
    except jwt.InvalidTokenError:
        raise AuthError("Invalid access token") from None

    # Парсим в Pydantic-модель — заодно валидируем sub как UUID
    try:
        payload = TokenPayload(**raw)
    except ValidationError:
        raise AuthError("Invalid token payload") from None

    # refresh-токены не должны пускать на API-эндпоинты
    if payload.type != "access":
        raise AuthError("Wrong token type")

    # Проверяем блок-лист (jti мог быть ревокнут при logout)
    if await redis.exists(f"revoked_jti:{payload.jti}"):
        raise AuthError("Access token has been revoked")

    return payload


async def get_token_payload_optional(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> TokenPayload | None:
    """Опционально декодирует JWT из заголовка Authorization.

    Возвращает None если заголовок отсутствует, токен невалиден или истёк.
    Используется в logout: если access-токен истёк, мы всё равно должны
    иметь возможность удалить refresh-cookie.
    """
    if authorization is None:
        return None
    if not authorization.startswith("Bearer "):
        return None
    token = authorization[7:].strip()
    if not token:
        return None
    try:
        raw: dict[str, Any] = decode_token(token)
    except jwt.InvalidTokenError:
        return None
    try:
        payload = TokenPayload(**raw)
    except ValidationError:
        return None
    if payload.type != "access":
        return None
    return payload


# ---------------------------------------------------------------------------
# 3. Текущий пользователь
# ---------------------------------------------------------------------------


async def get_current_user(
    payload: Annotated[TokenPayload, Depends(get_token_payload)],
    session: SessionDep,
) -> User:
    """Резолвит текущего пользователя по sub из токена.

    Проверяет, что пользователь существует в БД и не деактивирован.
    """
    user = await UserRepository(session).get_by_id(payload.sub)
    if user is None:
        raise AuthError("User not found")

    if not user.is_active:
        raise UserInactiveError(details={"user_id": str(user.id)})

    return user


# ---------------------------------------------------------------------------
# 4. Текущая организация (из связи user.organization_id)
# ---------------------------------------------------------------------------


async def get_current_organization(
    user: Annotated[User, Depends(get_current_user)],
    session: SessionDep,
) -> Organization:
    """Резолвит организацию, к которой привязан пользователь.

    Требуется для эндпоинтов, работающих в контексте организации
    (organizer, scanner, cashier). Суперадмины без организации получат
    OrganizationRequiredError.
    """
    if user.organization_id is None:
        raise OrganizationRequiredError()

    org = await OrganizationRepository(session).get_by_id(user.organization_id)
    if org is None:
        raise AuthError(
            "Organization not found for user",
            details={"organization_id": str(user.organization_id)},
        )

    if org.status == OrganizationStatus.SUSPENDED:
        raise OrganizationSuspendedError()

    # ACTIVE и PENDING_MODERATION — пропускаем.
    # PENDING_MODERATION — organizer должен видеть свой dashboard
    # с баннером «на модерации».

    # Сохраняем в contextvar для структурированных логов
    current_organization_id.set(org.id)

    return org


# ---------------------------------------------------------------------------
# 5. Ролевые guards
# ---------------------------------------------------------------------------


def require_roles(
    *allowed: UserRole,
) -> Callable[..., Awaitable[User]]:
    """Фабрика зависимости: пропускает только пользователей с нужной ролью.

    Использование:
        require_superadmin = require_roles(UserRole.SUPERADMIN)
        require_organizer_or_above = require_roles(
            UserRole.ORGANIZER, UserRole.SUPERADMIN
        )
    """

    async def _dep(
        user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if user.role not in allowed:
            raise InsufficientRoleError(
                details={
                    "required": [r.value for r in allowed],
                    "actual": user.role.value,
                }
            )
        return user

    return _dep


require_superadmin = require_roles(UserRole.SUPERADMIN)
require_organizer = require_roles(UserRole.ORGANIZER)
require_organizer_or_above = require_roles(UserRole.ORGANIZER, UserRole.SUPERADMIN)
require_scanner = require_roles(
    UserRole.SCANNER, UserRole.ORGANIZER, UserRole.SUPERADMIN
)


# ---------------------------------------------------------------------------
# 6. Tenant slug из middleware
# ---------------------------------------------------------------------------


async def get_tenant_slug(request: Request) -> str | None:
    """Возвращает slug арендатора, резолвенный `TenantMiddleware`.

    Middleware кладёт slug в `request.state.tenant_slug`.
    Если middleware не отработал — безопасно возвращаем None.
    """
    return getattr(request.state, "tenant_slug", None)


async def get_tenant_organization(
    slug: Annotated[str | None, Depends(get_tenant_slug)],
    session: SessionDep,
) -> Organization:
    """Резолвит организацию по slug из subdomain/header.

    Используется публичными роутами под subdomain (витрина, регистрация).
    Если slug не проставлен — ошибка (публичный роут требует tenant).
    """
    if slug is None:
        raise TenantNotResolvedError()

    org = await OrganizationRepository(session).get_by_slug(slug)
    if org is None:
        raise NotFoundError("Organization not found", details={"slug": slug})

    if org.status == OrganizationStatus.SUSPENDED:
        raise OrganizationSuspendedError()

    # PENDING_MODERATION и ACTIVE — пропускаем.
    # На странице логина до активации будет «на модерации».

    current_organization_id.set(org.id)

    return org


# ---------------------------------------------------------------------------
# 7. Типовые Annotated-алиасы для endpoint'ов
# ---------------------------------------------------------------------------


CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentOrganization = Annotated[Organization, Depends(get_current_organization)]
SuperadminUser = Annotated[User, Depends(require_superadmin)]
OrganizerUser = Annotated[User, Depends(require_organizer)]
ScannerUser = Annotated[User, Depends(require_scanner)]
TenantOrganization = Annotated[Organization, Depends(get_tenant_organization)]
