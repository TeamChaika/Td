"""Async-подключение к PostgreSQL через SQLAlchemy.

Единая точка инициализации движка и сессий.
Использовать `get_session` как FastAPI dependency.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from paytools.core.config import get_settings

_settings = get_settings()

# Движок создаётся один раз на процесс. `pool_pre_ping=True` автоматически
# проверяет соединение перед выдачей — полезно при сетевых сбоях.
engine: AsyncEngine = create_async_engine(
    _settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=1800,
)

# Фабрика сессий. `expire_on_commit=False` — объекты остаются доступными после commit.
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency для FastAPI: выдаёт сессию с auto-commit/rollback.

    При успешном завершении endpoint'а — commit. При исключении — rollback.
    Сессия закрывается автоматически в async with.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()


async def dispose_engine() -> None:
    """Закрывает движок при shutdown приложения."""
    await engine.dispose()
