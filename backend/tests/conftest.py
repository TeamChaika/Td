"""Общие pytest-фикстуры для unit и integration тестов.

Использует:
- PostgreSQL из docker-compose (отдельная БД tdpay_test)
- fakeredis для Redis (in-memory)
- Транзакционный rollback после каждого теста
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from fakeredis import FakeAsyncRedis
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from paytools.core.config import Settings, get_settings
from paytools.core.db import get_session
from paytools.core.redis import get_redis_client
from paytools.core.security import hash_password
from paytools.db.models.enums import OrganizationStatus, UserRole
from paytools.db.models.organization import Organization
from paytools.db.models.user import User
from paytools.db.repositories.organization import OrganizationRepository
from paytools.db.repositories.user import UserRepository
from paytools.main import app

# ---------------------------------------------------------------------------
# Тестовые константы
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "postgresql+asyncpg://tdpay:tdpay@localhost:5432/tdpay_test"

# 44 chars, valid Fernet
TEST_FERNET_KEY = "DoS7l0dqk2ewkyuqDsLLWpTi1i2FWzA_AZAjjuHQXKg="
TEST_SECRET_KEY = "test-secret-key-at-least-32-chars!!"
TEST_JWT_SECRET = "test-jwt-secret-at-least-32-chars!!"

# ---------------------------------------------------------------------------
# Настройки для тестов
# ---------------------------------------------------------------------------


def _build_test_settings() -> Settings:
    """Создать Settings с тестовыми значениями."""
    return Settings(
        env="test",
        database_url=TEST_DATABASE_URL,
        redis_url="redis://localhost:6379/0",
        secret_key=TEST_SECRET_KEY,
        fernet_key=TEST_FERNET_KEY,
        jwt_secret=TEST_JWT_SECRET,
        jwt_access_ttl_min=15,
        jwt_refresh_ttl_days=30,
        s3_endpoint="http://localhost:9000",
        s3_bucket="tdpay-test",
        s3_access_key="minioadmin",
        s3_secret_key="minioadmin",
        s3_region="ru-1",
        smtp_host="localhost",
        smtp_port=1025,
        smtp_from="test@tdpay.local",
        platform_domain="tdpay.local",
        platform_url="http://localhost:3000",
    )


# ---------------------------------------------------------------------------
# Фикстуры БД
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Тестовые настройки (сессионная фикстура)."""
    return _build_test_settings()


@pytest_asyncio.fixture(scope="session")
async def async_engine(test_settings: Settings) -> AsyncIterator[AsyncEngine]:
    """Создаёт async-движок для тестовой БД (сессионный).

    Используем NullPool чтобы избежать конфликтов «another operation
    is in progress» между сессией теста и сессией TenantMiddleware.
    """
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(
        test_settings.database_url,
        echo=False,
        poolclass=NullPool,
    )
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def async_session(
    async_engine: AsyncEngine,
) -> AsyncIterator[AsyncSession]:
    """Создаёт сессию с откатом после каждого теста.

    Каждый тест работает в своей сессии. После теста все изменения
    откатываются — БД остаётся чистой для следующего теста.

    Не используем session.begin() чтобы избежать конфликта с
    TenantMiddleware, который создаёт свою сессию для резолва tenant.
    Вместо этого делаем rollback вручную после теста.
    """
    async_session_factory = async_sessionmaker(
        bind=async_engine,
        expire_on_commit=False,
        class_=AsyncSession,
        autoflush=False,
    )
    async with async_session_factory() as session:
        yield session
        await session.rollback()


# ---------------------------------------------------------------------------
# Фикстуры Redis (fakeredis)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def fake_redis() -> AsyncIterator[Redis[str]]:
    """In-memory fakeredis-клиент, заменяющий настоящий Redis."""
    fr = FakeAsyncRedis(decode_responses=True)
    yield fr  # type: ignore[return-value]
    await fr.aclose()  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Фикстуры FastAPI app + client
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def app_with_overrides(
    async_session: AsyncSession,
    async_engine: AsyncEngine,
    fake_redis: Redis[str],
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[Any]:
    """FastAPI app с переопределёнными зависимостями (БД + Redis + settings).

    Переопределяет:
    - get_session → тестовая сессия с транзакционным rollback
    - get_redis_client → fakeredis
    - get_settings → тестовые настройки
    - AsyncSessionLocal в tenancy → тестовая фабрика сессий
    """
    test_settings = _build_test_settings()

    # Переопределяем get_settings через monkeypatch
    monkeypatch.setattr(
        "paytools.core.config.get_settings",
        lambda: test_settings,
    )
    monkeypatch.setattr(
        "paytools.core.security._settings",
        test_settings,
    )
    # Сбрасываем lru_cache на get_settings
    get_settings.cache_clear()

    # Переопределяем AsyncSessionLocal в tenancy.py чтобы middleware
    # использовал тестовый движок, а не продакшн
    test_session_factory = async_sessionmaker(
        bind=async_engine,
        expire_on_commit=False,
        class_=AsyncSession,
        autoflush=False,
    )
    monkeypatch.setattr(
        "paytools.core.tenancy.AsyncSessionLocal",
        test_session_factory,
    )

    # Переопределяем зависимости FastAPI
    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield async_session

    async def override_get_redis() -> Redis:  # type: ignore[type-arg]
        return fake_redis

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_redis_client] = override_get_redis

    # Также переопределяем get_redis из deps (если используется)
    from paytools.api.v1.deps import get_redis as deps_get_redis

    app.dependency_overrides[deps_get_redis] = override_get_redis

    # Переопределяем get_redis_client на уровне модуля — эндпоинты
    # вызывают её напрямую (не через DI) в _build_*_service
    monkeypatch.setattr(
        "paytools.core.redis.get_redis_client",
        lambda: fake_redis,
    )
    # Также переопределяем в api-слое (импортируется локально)
    monkeypatch.setattr(
        "paytools.api.v1.auth.routes.get_redis_client",
        lambda: fake_redis,
    )
    monkeypatch.setattr(
        "paytools.api.v1.public.organizations.get_redis_client",
        lambda: fake_redis,
    )
    monkeypatch.setattr(
        "paytools.api.v1.admin.organizations.get_redis_client",
        lambda: fake_redis,
    )
    monkeypatch.setattr(
        "paytools.api.v1.organizer.organization.get_redis_client",
        lambda: fake_redis,
    )
    monkeypatch.setattr(
        "paytools.core.tenancy.get_redis_client",
        lambda: fake_redis,
    )

    yield app

    # Очистка
    app.dependency_overrides.clear()
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def client(
    app_with_overrides: Any,
) -> AsyncIterator[AsyncClient]:
    """httpx.AsyncClient, подключённый к тестовому FastAPI app."""
    transport = ASGITransport(app=app_with_overrides)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Фикстуры готовых пользователей
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def superadmin_user(async_session: AsyncSession) -> User:
    """Создаёт superadmin-пользователя в тестовой БД."""
    user_repo = UserRepository(async_session)
    user = await user_repo.create(
        email="superadmin@tdpay.example.com",
        password_hash=hash_password("SuperAdmin123!"),
        first_name="Super",
        last_name="Admin",
        role=UserRole.SUPERADMIN,
        is_active=True,
    )
    return user


@pytest_asyncio.fixture
async def organizer_user(async_session: AsyncSession) -> User:
    """Создаёт организацию и пользователя-organizer в тестовой БД."""
    org_repo = OrganizationRepository(async_session)
    user_repo = UserRepository(async_session)

    org = await org_repo.create(
        slug="test-org",
        name="Test Organization",
        status=OrganizationStatus.ACTIVE,
    )
    user = await user_repo.create(
        email="organizer@test-org.example.com",
        password_hash=hash_password("Organizer123!"),
        first_name="Test",
        last_name="Organizer",
        role=UserRole.ORGANIZER,
        is_active=True,
        organization_id=org.id,
    )
    return user


# ---------------------------------------------------------------------------
# Хелперы
# ---------------------------------------------------------------------------


async def create_org_with_user(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    first_name: str = "Test",
    last_name: str = "User",
    org_name: str = "Test Org",
    org_slug: str,
    org_status: OrganizationStatus = OrganizationStatus.ACTIVE,
) -> tuple[Organization, User]:
    """Хелпер: создать организацию с пользователем-organizer."""
    org_repo = OrganizationRepository(session)
    user_repo = UserRepository(session)

    org = await org_repo.create(
        slug=org_slug,
        name=org_name,
        status=org_status,
    )
    user = await user_repo.create(
        email=email,
        password_hash=hash_password(password),
        first_name=first_name,
        last_name=last_name,
        role=UserRole.ORGANIZER,
        is_active=True,
        organization_id=org.id,
    )
    return org, user


async def login_and_get_tokens(
    client: AsyncClient,
    email: str,
    password: str,
) -> dict[str, Any]:
    """Хелпер: залогиниться и получить access_token + cookies."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    return {
        "status_code": resp.status_code,
        "body": resp.json(),
        "cookies": resp.cookies,
    }


def auth_header(token: str) -> dict[str, str]:
    """Хелпер: заголовок Authorization с Bearer-токеном."""
    return {"Authorization": f"Bearer {token}"}
