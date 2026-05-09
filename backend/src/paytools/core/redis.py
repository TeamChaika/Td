"""Redis-клиент для кэша, rate-limit, magic-link токенов и очередей arq."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from redis.asyncio import Redis

from paytools.core.config import get_settings

_settings = get_settings()

if TYPE_CHECKING:
    # types-redis объявляет Redis как generic класс Redis[str],
    # но runtime redis-py (до версии 5) не является generic.
    # Оборачиваем через TYPE_CHECKING чтобы FastAPI не пытался
    # eval'ить Redis[str] в inspect.signature(eval_str=True).
    _RedisType = Redis[str]
else:
    _RedisType = Redis

# Один клиент на процесс. `decode_responses=True` — строки вместо bytes.
_redis_client: _RedisType | None = None


def get_redis_client() -> _RedisType:
    """Возвращает singleton Redis-клиента."""
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(
            _settings.redis_url,
            decode_responses=True,
            socket_keepalive=True,
        )
    return _redis_client


async def get_redis() -> AsyncGenerator[_RedisType, None]:
    """FastAPI dependency для Redis."""
    yield get_redis_client()


async def close_redis() -> None:
    """Закрывает Redis-подключение при shutdown."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
