"""Middleware: генерация / проброс X-Request-Id и его привязка к логам."""

from __future__ import annotations

import uuid
from typing import cast

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Присваивает каждому запросу request_id.

    Если клиент прислал `X-Request-Id` — используем его (удобно для трейсинга).
    Иначе генерируем новый uuid4.
    Request_id попадает в structlog-contextvars → автоматически во все логи
    запроса, и возвращается в ответе.
    """

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id

        structlog.contextvars.bind_contextvars(request_id=request_id)
        try:
            response = cast(Response, await call_next(request))
        finally:
            structlog.contextvars.unbind_contextvars("request_id")

        response.headers["x-request-id"] = request_id
        return response
