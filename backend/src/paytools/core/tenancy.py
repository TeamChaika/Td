"""Multi-tenancy: определение текущей организации в контексте запроса.

Middleware наполняет contextvars (для логов) и request.state (для FastAPI-зависимостей).
Проверки прав и блокировки — в слое Depends, не здесь.
"""

from __future__ import annotations

import json
from contextvars import ContextVar
from uuid import UUID

import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from paytools.core.config import get_settings
from paytools.core.db import AsyncSessionLocal
from paytools.core.redis import get_redis_client
from paytools.core.security import decode_token
from paytools.db.repositories.organization import OrganizationRepository

# --------------------------- Константы ---------------------------

# TTL кэша tenant slug → org_id (секунды)
_TENANT_CACHE_TTL: int = 60

# --------------------------- Контекстные переменные ---------------------------

# Slug текущего арендатора (из subdomain / заголовка).
current_tenant_slug: ContextVar[str | None] = ContextVar(
    "current_tenant_slug", default=None
)
# UUID текущей организации (из JWT или резолва slug → БД).
current_organization_id: ContextVar[UUID | None] = ContextVar(
    "current_organization_id", default=None
)


def _extract_slug_from_host(host: str, platform_domain: str) -> str | None:
    """Возвращает поддомен, если хост выглядит как `<slug>.<platform_domain>`.

    Корневой домен (`tdpay.ru`, `www.tdpay.ru`) → None (это лендинг).
    В dev-режиме также поддерживаем `<slug>.localhost`.
    """
    # Убираем порт
    hostname = host.split(":", maxsplit=1)[0].lower().strip()

    # Корневой домен — не tenant
    if hostname in {platform_domain, f"www.{platform_domain}"}:
        return None

    # Поддомен платформы: <slug>.<platform_domain>
    suffix = f".{platform_domain}"
    if hostname.endswith(suffix):
        slug = hostname[: -len(suffix)]
        if slug and "." not in slug:  # отбрасываем вложенные поддомены
            return slug

    # Dev-удобство: <slug>.localhost
    if hostname.endswith(".localhost"):
        slug = hostname[: -len(".localhost")]
        if slug and "." not in slug:
            return slug

    return None


def _try_extract_org_from_jwt(request: Request) -> UUID | None:
    """Безопасно декодирует JWT и возвращает organization_id из claim ``org``.

    Любая ошибка декодирования/парсинга — возвращаем None. Middleware
    не должен падать из-за невалидного токена — это задача depends-ов.

    Проверяет ``type`` claim: только access-токены учитываются.
    Refresh-токены не должны влиять на tenant resolution.
    """
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return None
    token = auth[7:].strip()
    if not token:
        return None
    try:
        payload = decode_token(token)
    except jwt.InvalidTokenError:
        return None

    # Только access-токены несут контекст организации
    if payload.get("type") != "access":
        return None

    org_str = payload.get("org")
    if not org_str:
        return None
    try:
        return UUID(org_str)
    except (ValueError, TypeError):
        return None


async def _resolve_org_id_from_slug(slug: str) -> UUID | None:
    """Загружает organization_id по slug из БД (с Redis-кешем).

    Сначала проверяет Redis (ключ ``tenant_slug:{slug_lower}``).
    При cache miss — SELECT из БД + SETEX в Redis с TTL 60 сек.

    Возвращает org_id только если статус организации — ``active``.
    Для ``suspended`` / ``pending_moderation`` возвращает None — такие
    tenant'ы не должны попадать в публичный контекст.
    """
    slug_lower = slug.lower()
    cache_key = f"tenant_slug:{slug_lower}"

    redis = get_redis_client()

    # 1. Redis cache lookup
    try:
        cached = await redis.get(cache_key)
    except Exception:
        cached = None

    if cached is not None:
        try:
            data: dict[str, str] = json.loads(cached)
            org_id_str = data.get("org_id")
            status = data.get("status", "")
            if org_id_str and status == "active":
                return UUID(org_id_str)
            # Статус не active (suspended/pending) — не возвращаем
            return None
        except (json.JSONDecodeError, ValueError, TypeError):
            # Кеш повреждён — идём в БД
            pass

    # 2. Cache miss — БД
    async with AsyncSessionLocal() as session:
        repo = OrganizationRepository(session)
        try:
            org = await repo.get_by_slug(slug_lower)
        except Exception:
            return None

    if org is None:
        return None

    # 3. Сохраняем в кеш (best-effort)
    try:
        cache_data = json.dumps(
            {
                "org_id": str(org.id),
                "status": org.status.value,
            }
        )
        await redis.setex(cache_key, _TENANT_CACHE_TTL, cache_data)
    except Exception:
        pass

    return org.id if org.status.value == "active" else None


class TenantMiddleware(BaseHTTPMiddleware):
    """Кладёт slug арендатора и organization_id в contextvars.

    Порядок определения:
    1. Из JWT (Authorization: Bearer) — если декодируется и содержит ``org``.
    2. Из заголовка X-Tenant-Slug или Host subdomain — для публичных роутов.

    JWT имеет приоритет: если пользователь залогинен, его организация
    берётся из токена, а не из subdomain — это защищает от ситуации,
    когда organizer A открыл домен org-B и делает запросы под своим токеном.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._platform_domain = get_settings().platform_domain

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        # --- 1. Slug из Host/Header (для логов и публичных роутов) ---
        slug = request.headers.get("x-tenant-slug")
        if not slug:
            host = request.headers.get("host", "")
            slug = _extract_slug_from_host(host, self._platform_domain)

        # --- 2. organization_id из JWT, если есть ---
        org_id_from_jwt = _try_extract_org_from_jwt(request)

        # --- 3. organization_id из БД по slug, если slug есть и JWT не дал ---
        org_id_from_slug: UUID | None = None
        if org_id_from_jwt is None and slug:
            org_id_from_slug = await _resolve_org_id_from_slug(slug)

        resolved_org_id = org_id_from_jwt or org_id_from_slug

        # --- 4. Устанавливаем contextvars на время запроса ---
        request.state.tenant_slug = slug
        request.state.organization_id = resolved_org_id

        slug_token = current_tenant_slug.set(slug)
        org_token = current_organization_id.set(resolved_org_id)
        try:
            response: Response = await call_next(request)
        finally:
            current_tenant_slug.reset(slug_token)
            current_organization_id.reset(org_token)

        if slug:
            response.headers["x-resolved-tenant"] = slug
        return response
