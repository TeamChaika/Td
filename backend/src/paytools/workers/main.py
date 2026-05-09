"""Arq-воркер для фоновых задач.

В MVP (Phase 1-6) таски будут добавляться постепенно:
- Phase 4: `expire_draft_reservations`
- Phase 5: `issue_tickets`, `render_ticket_pdf`, `process_qrm_webhook`
- Phase 6: `send_ticket_email`, `send_ticket_sms`, `schedule_event_reminders`
"""

from __future__ import annotations

from typing import Any, ClassVar

from arq.connections import RedisSettings
from arq.cron import cron

from paytools.core.config import get_settings
from paytools.core.logging import setup_logging
from paytools.workers.tasks.bookings import expire_draft_reservations


def _redis_settings() -> RedisSettings:
    """Собирает RedisSettings из URL."""
    from urllib.parse import urlparse

    settings = get_settings()
    parsed = urlparse(settings.redis_url)
    return RedisSettings(
        host=parsed.hostname or "redis",
        port=parsed.port or 6379,
        database=int((parsed.path or "/0").lstrip("/") or 0),
        password=parsed.password,
    )


async def on_startup(ctx: dict[str, Any]) -> None:
    """Инициализация воркера (логи, БД-движок можно добавить при необходимости)."""
    setup_logging()


async def on_shutdown(ctx: dict[str, Any]) -> None:
    """Корректное закрытие ресурсов."""
    from paytools.core.db import dispose_engine
    from paytools.core.redis import close_redis

    await dispose_engine()
    await close_redis()


class WorkerSettings:
    """Настройки arq-воркера."""

    functions: ClassVar[list[Any]] = []  # Phase 5+ добавит реальные задачи
    cron_jobs: ClassVar[list[Any]] = [
        # Запуск каждую минуту: second=0, все остальные поля по умолчанию (каждую)
        cron(expire_draft_reservations, second=0, run_at_startup=True),
    ]
    on_startup = on_startup
    on_shutdown = on_shutdown
    redis_settings = _redis_settings()
    max_jobs = 10
    keep_result = 3600  # 1 час
