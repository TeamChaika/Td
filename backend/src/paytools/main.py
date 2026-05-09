"""Точка входа FastAPI-приложения TD Pay.

Включает middleware (request-id, tenant), exception handlers и все роутеры v1.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from paytools import __version__
from paytools.api.v1 import v1_router
from paytools.api.v1.deps import RedisDep, SessionDep
from paytools.core.config import get_settings
from paytools.core.db import dispose_engine
from paytools.core.errors import DomainError
from paytools.core.exception_handlers import (
    domain_error_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_error_handler,
)
from paytools.core.logging import get_logger, setup_logging
from paytools.core.redis import close_redis
from paytools.core.request_id import RequestIdMiddleware
from paytools.core.tenancy import TenantMiddleware
from paytools.integrations.storage.s3 import S3Config, S3Storage


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Жизненный цикл приложения: startup и shutdown."""
    setup_logging()
    logger = get_logger("paytools.startup")
    settings = get_settings()
    logger.info(
        "application_started",
        env=settings.env,
        platform_domain=settings.platform_domain,
        version=__version__,
    )

    # Идемпотентно создаём S3-бакет если не существует.
    # Не блокируем запуск при недоступности S3 (dev без MinIO).
    try:
        s3_config = S3Config(
            endpoint_url=settings.s3_endpoint,
            bucket=settings.s3_bucket,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            region=settings.s3_region,
            public_endpoint=settings.s3_public_endpoint,
        )
        s3_storage = S3Storage(s3_config)
        await s3_storage.ensure_bucket()
        logger.info("s3_bucket_ensured", bucket=settings.s3_bucket)
    except Exception:
        logger.warning(
            "s3_bucket_ensure_failed",
            bucket=settings.s3_bucket,
            exc_info=True,
        )

    try:
        yield
    finally:
        logger.info("application_shutdown")
        await dispose_engine()
        await close_redis()


def _build_cors_origins() -> tuple[list[str], str | None]:
    """Список явных origin-ов + regex для wildcard-поддоменов."""
    settings = get_settings()
    explicit = [
        settings.platform_url,
        f"https://{settings.platform_domain}",
        f"http://{settings.platform_domain}",
    ]
    # Regex для `*.tdpay.ru` / `*.tdpay.local` / `*.localhost`
    escaped = settings.platform_domain.replace(".", r"\.")
    wildcard = rf"^https?://[a-z0-9-]+\.({escaped}|localhost)(:\d+)?$"
    return explicit, wildcard


app = FastAPI(
    title="TD Pay API",
    version=__version__,
    description="Tickets & Deposits Pay — платформа продажи билетов.",
    lifespan=lifespan,
)

# --- CORS ---
_cors_origins, _cors_regex = _build_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=_cors_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["x-request-id", "x-resolved-tenant"],
)

# --- Наши middleware (порядок важен: сначала tenant, потом request-id,
# чтобы request_id попал в логи, где уже есть tenant) ---
app.add_middleware(TenantMiddleware)
app.add_middleware(RequestIdMiddleware)

# --- Exception handlers ---
app.add_exception_handler(DomainError, domain_error_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# --- Роутеры ---
app.include_router(v1_router, prefix="/api/v1")


@app.get("/health", tags=["system"], summary="Liveness probe")
async def health() -> dict[str, str]:
    """Отвечает всегда, если процесс жив."""
    return {"status": "ok"}


@app.get("/ready", tags=["system"], summary="Readiness probe")
async def ready(db: SessionDep, redis: RedisDep) -> dict[str, str]:
    """Проверяет доступность БД и Redis."""
    await db.execute(text("SELECT 1"))
    await redis.ping()
    return {"status": "ok"}
