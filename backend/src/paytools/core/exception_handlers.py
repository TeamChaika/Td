"""FastAPI exception handlers для единого формата ошибок."""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from paytools.core.errors import DomainError


def _error_body(
    code: str,
    message: str,
    *,
    details: Any = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        body["details"] = jsonable_encoder(details)
    if request_id:
        body["request_id"] = request_id
    return {"error": body}


async def domain_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Преобразует DomainError → JSONResponse единого формата."""
    assert isinstance(exc, DomainError)
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(
            exc.code,
            exc.message,
            details=exc.details,
            request_id=request_id,
        ),
    )


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Приводим стандартные HTTPException к нашему формату."""
    assert isinstance(exc, HTTPException)
    request_id = getattr(request.state, "request_id", None)
    # Маппинг стандартных кодов на наши
    code_map = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        405: "method_not_allowed",
        409: "conflict",
        429: "rate_limited",
    }
    code = code_map.get(exc.status_code, "http_error")
    message = exc.detail if isinstance(exc.detail, str) else "Ошибка запроса"
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(code, message, request_id=request_id),
    )


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Ошибки валидации Pydantic → 400 с деталями по полям."""
    assert isinstance(exc, RequestValidationError)
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=400,
        content=_error_body(
            "validation_error",
            "Некорректные данные запроса",
            details={"errors": exc.errors()},
            request_id=request_id,
        ),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Последняя линия обороны: неожиданное исключение → 500 без деталей."""
    import structlog

    logger = structlog.stdlib.get_logger("paytools.unhandled")
    logger.exception("unhandled_exception", exc_info=exc)
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=500,
        content=_error_body(
            "internal_error",
            "Внутренняя ошибка сервера",
            request_id=request_id,
        ),
    )
