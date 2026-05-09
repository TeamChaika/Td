"""Настройка structlog + контекстные переменные для логов.

В dev — читаемый консольный рендер, в prod — JSON.
Автоматически подхватывает request_id / organization_id / user_id
из contextvars (если были выставлены middleware).
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from paytools.core.config import get_settings

# ---------------------------------------------------------------------------
# Список ключей, значения которых не должны попасть в логи.
# Сравнение регистро-нечувствительное (lowercase).
# ---------------------------------------------------------------------------

_SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "password",
        "password_hash",
        "qrm_api_key",
        "qrm_api_key_encrypted",
        "refresh_token",
        "access_token",
        "token",
        "jwt",
        "authorization",
        "cookie",
        "set-cookie",
        "magic_link_token",
        "magic_token",
    }
)


def _redact_sensitive(
    _logger: Any,
    _method_name: str,
    event_dict: structlog.types.EventDict,
) -> structlog.types.EventDict:
    """Процессор structlog: рекурсивно заменяет секретные поля на ``"***"``.

    Зачем: секретные ключи/токены/пароли не должны утекать в системы сбора
    логов (ELK, DataDog, etc.). Процессор работает до JSONRenderer/ConsoleRenderer,
    поэтому гарантирует redact и в JSON-выводе, и в dev-консоли.

    Ключи сравниваются в lowercase. Обрабатываются вложенные dict и list.
    """

    def _recursive(obj: object) -> object:
        if isinstance(obj, dict):
            result: dict[str, object] = {}
            for k, v in obj.items():
                if isinstance(k, str) and k.lower() in _SENSITIVE_KEYS:
                    result[k] = "***"
                else:
                    result[k] = _recursive(v)
            return result
        if isinstance(obj, list):
            return [_recursive(v) for v in obj]
        return obj

    redacted = _recursive(event_dict)
    assert isinstance(redacted, dict)
    return redacted


def setup_logging() -> None:
    """Инициализирует structlog и stdlib-logging."""
    settings = get_settings()
    is_dev = settings.is_dev

    # Общие процессоры — применяются и к structlog, и к stdlib-логам
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        _redact_sensitive,  # ДО рендера — чтобы секреты не попали в вывод
    ]

    if is_dev:
        # Консоль в цвете, читаемо
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer(
            colors=True,
        )
    else:
        # JSON на каждой строке — удобно для grep/collector'ов
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Связываем stdlib logging (uvicorn, sqlalchemy, httpx) со structlog
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                renderer,
            ],
        )
    )

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(logging.DEBUG if is_dev else logging.INFO)

    # Приглушаем слишком шумные логгеры
    for noisy in ("sqlalchemy.engine", "uvicorn.access", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Получить typed-логгер."""
    return structlog.stdlib.get_logger(name)
