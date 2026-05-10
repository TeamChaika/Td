"""Auth endpoints: login, refresh, logout, me, magic-link.

Cookie policy:
- Имя: ``tdpay_refresh``
- httpOnly, SameSite=Lax, path=/
- secure=True только в prod
- max_age из ``jwt_refresh_ttl_days``
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from paytools.api.v1.deps import CurrentUser, SessionDep, TokenPayload
from paytools.api.v1.deps import get_token_payload_optional as _get_token_payload_opt
from paytools.api.v1.schemas.auth import (
    LoginRequest,
    MagicLinkRequestSchema,
    MagicLinkVerifySchema,
    MeResponse,
    TokenPair,
)
from paytools.core.config import get_settings
from paytools.core.redis import get_redis_client
from paytools.db.repositories.audit import AuditLogRepository
from paytools.db.repositories.email_blocklist import EmailBlocklistRepository
from paytools.db.repositories.organization import OrganizationRepository
from paytools.db.repositories.user import UserRepository
from paytools.domain.audit.service import AuditService
from paytools.domain.auth.errors import InvalidRefreshTokenError
from paytools.domain.auth.magic_link import MagicLinkService
from paytools.domain.auth.service import AuthService
from paytools.domain.auth.service import TokenPair as DomainTokenPair
from paytools.domain.organizations.service import OrganizationService

router = APIRouter()


# ---------------------------------------------------------------------------
# Cookie helpers
# ---------------------------------------------------------------------------


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """Установить httpOnly cookie ``tdpay_refresh`` с refresh-токеном."""
    settings = get_settings()
    response.set_cookie(
        key="tdpay_refresh",
        value=refresh_token,
        max_age=settings.jwt_refresh_ttl_days * 24 * 3600,
        httponly=True,
        secure=settings.is_prod,
        samesite="lax",
        path="/",
    )


def _clear_refresh_cookie(response: Response) -> None:
    """Удалить httpOnly cookie ``tdpay_refresh`` при logout."""
    response.delete_cookie(
        key="tdpay_refresh",
        path="/",
        httponly=True,
        secure=get_settings().is_prod,
        samesite="lax",
    )


def _read_refresh_cookie(request: Request) -> str | None:
    """Прочитать refresh-токен из httpOnly cookie ``tdpay_refresh``."""
    return request.cookies.get("tdpay_refresh")


# ---------------------------------------------------------------------------
# DI-хелперы (ручная сборка, без IoC-контейнера)
# ---------------------------------------------------------------------------


def _build_auth_service(session: AsyncSession) -> AuthService:
    """Собрать AuthService со всеми зависимостями (репо, org_service, audit, redis)."""
    user_repo = UserRepository(session)
    org_repo = OrganizationRepository(session)
    email_blocklist_repo = EmailBlocklistRepository(session)
    audit_repo = AuditLogRepository(session, organization_id=None)
    audit_service = AuditService(session, repo=audit_repo)
    redis = get_redis_client()
    org_service = OrganizationService(
        session,
        org_repo=org_repo,
        user_repo=user_repo,
        audit_service=audit_service,
        redis=redis,
    )
    return AuthService(
        session,
        user_repo=user_repo,
        org_service=org_service,
        redis=redis,
        email_blocklist_repo=email_blocklist_repo,
        org_repo=org_repo,
        audit_service=audit_service,
    )


def _build_magic_link_service(
    session: AsyncSession, auth_service: AuthService
) -> MagicLinkService:
    """Собрать MagicLinkService с переданным AuthService (общий redis, сессия)."""
    user_repo = UserRepository(session)
    org_repo = OrganizationRepository(session)
    email_blocklist_repo = EmailBlocklistRepository(session)
    audit_repo = AuditLogRepository(session, organization_id=None)
    audit_service = AuditService(session, repo=audit_repo)
    redis = get_redis_client()
    return MagicLinkService(
        session,
        user_repo=user_repo,
        auth_service=auth_service,
        redis=redis,
        email_blocklist_repo=email_blocklist_repo,
        org_repo=org_repo,
        audit_service=audit_service,
    )


# ---------------------------------------------------------------------------
# 1. POST /auth/login
# ---------------------------------------------------------------------------


@router.post(
    "/login",
    response_model=TokenPair,
    summary="Вход по email+паролю",
    tags=["auth"],
)
async def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    session: SessionDep,
) -> TokenPair:
    """Аутентифицировать пользователя по email и паролю.

    Возвращает access-токен в теле ответа. Refresh-токен устанавливается
    в httpOnly cookie ``tdpay_refresh`` и недоступен из JavaScript.
    """
    auth_service = _build_auth_service(session)
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    domain_tokens: DomainTokenPair = await auth_service.login(
        data.email, data.password, ip=ip, user_agent=user_agent
    )
    _set_refresh_cookie(response, domain_tokens.refresh_token)
    return TokenPair(
        access_token=domain_tokens.access_token,
        token_type="bearer",
        expires_in=domain_tokens.access_expires_in,
    )


# ---------------------------------------------------------------------------
# 2. POST /auth/refresh
# ---------------------------------------------------------------------------


@router.post(
    "/refresh",
    response_model=TokenPair,
    summary="Обновить access-токен",
    tags=["auth"],
)
async def refresh(
    request: Request,
    response: Response,
    session: SessionDep,
) -> TokenPair:
    """Обновить пару токенов по refresh-токену из cookie (rotating refresh).

    Старый refresh-токен добавляется в блок-лист Redis — один токен
    можно использовать только один раз. Новый refresh устанавливается
    в cookie, заменяя старый.
    """
    refresh_token = _read_refresh_cookie(request)
    if refresh_token is None:
        raise InvalidRefreshTokenError("Missing refresh cookie")

    auth_service = _build_auth_service(session)
    domain_tokens: DomainTokenPair = await auth_service.refresh(refresh_token)
    _set_refresh_cookie(response, domain_tokens.refresh_token)
    return TokenPair(
        access_token=domain_tokens.access_token,
        token_type="bearer",
        expires_in=domain_tokens.access_expires_in,
    )


# ---------------------------------------------------------------------------
# 3. POST /auth/logout
# ---------------------------------------------------------------------------


OptionalTokenPayload = Annotated["TokenPayload | None", Depends(_get_token_payload_opt)]


@router.post(
    "/logout",
    status_code=204,
    summary="Выход",
    tags=["auth"],
)
async def logout(
    request: Request,
    response: Response,
    session: SessionDep,
    token_payload: OptionalTokenPayload,
) -> None:
    """Разлогинить пользователя: отозвать refresh-токен и access-токен, удалить cookie.

    Идемпотентный: если токен уже невалиден или отсутствует — cookie
    всё равно очищается, результат один и тот же.
    """
    refresh_token = _read_refresh_cookie(request)
    if refresh_token is not None:
        auth_service = _build_auth_service(session)
        access_jti: str | None = token_payload.jti if token_payload else None
        access_exp: int | None = token_payload.exp if token_payload else None
        ip = request.client.host if request.client else None
        # Пытаемся загрузить пользователя для аудита (опционально)
        user_for_audit = None
        if token_payload is not None:
            user_for_audit = await UserRepository(session).get_by_id(token_payload.sub)
        await auth_service.logout(
            refresh_token,
            access_jti=access_jti,
            access_exp=access_exp,
            user=user_for_audit,
            ip=ip,
        )
    _clear_refresh_cookie(response)


# ---------------------------------------------------------------------------
# 4. GET /auth/me
# ---------------------------------------------------------------------------


@router.get(
    "/me",
    response_model=MeResponse,
    summary="Текущий пользователь",
    tags=["auth"],
)
async def me(
    user: CurrentUser,
    session: SessionDep,
) -> MeResponse:
    """Вернуть информацию о текущем аутентифицированном пользователе.

    Если пользователь привязан к организации — возвращаются также
    slug и статус организации.
    """
    org_slug: str | None = None
    org_status = None

    if user.organization_id is not None:
        org = await OrganizationRepository(session).get_by_id(user.organization_id)
        if org is not None:
            org_slug = org.slug
            org_status = org.status

    return MeResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role,
        organization_id=user.organization_id,
        organization_slug=org_slug,
        organization_status=org_status,
    )


# ---------------------------------------------------------------------------
# 5. POST /auth/magic-link/request
# ---------------------------------------------------------------------------


@router.post(
    "/magic-link/request",
    status_code=202,
    summary="Запросить magic-link",
    tags=["auth"],
    responses={202: {"description": "Заявка принята"}},
)
async def request_magic_link(
    data: MagicLinkRequestSchema,
    session: SessionDep,
) -> dict[str, str]:
    """Отправить одноразовую ссылку для входа на email.

    Всегда возвращает 202 Accepted, независимо от того, существует ли
    пользователь с таким email — защита от перебора (user enumeration).
    """
    auth_service = _build_auth_service(session)
    ml_service = _build_magic_link_service(session, auth_service)
    await ml_service.request_magic_link(data.email)
    return {"status": "accepted"}


# ---------------------------------------------------------------------------
# 6. POST /auth/magic-link/verify
# ---------------------------------------------------------------------------


@router.post(
    "/magic-link/verify",
    response_model=TokenPair,
    summary="Подтвердить magic-link",
    tags=["auth"],
)
async def verify_magic_link(
    data: MagicLinkVerifySchema,
    response: Response,
    session: SessionDep,
) -> TokenPair:
    """Проверить одноразовый magic-link токен и выдать пару JWT.

    Токен атомарно удаляется из Redis при первом использовании.
    При успехе — refresh-токен в httpOnly cookie, access — в теле.
    """
    auth_service = _build_auth_service(session)
    ml_service = _build_magic_link_service(session, auth_service)
    domain_tokens: DomainTokenPair = await ml_service.verify_magic_link(data.token)
    _set_refresh_cookie(response, domain_tokens.refresh_token)
    return TokenPair(
        access_token=domain_tokens.access_token,
        token_type="bearer",
        expires_in=domain_tokens.access_expires_in,
    )
