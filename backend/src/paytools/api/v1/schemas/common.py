"""Общие схемы: формат ошибок, пагинация."""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Детали ошибки в едином формате."""

    code: str = Field(description="Машиночитаемый код ошибки")
    message: str = Field(description="Читаемое описание для пользователя")
    details: dict[str, Any] | None = Field(
        default=None, description="Дополнительные детали (поля, значения)"
    )
    request_id: str | None = Field(default=None, description="ID запроса для трейсинга")


class ErrorResponse(BaseModel):
    """Обёртка ошибки: `{"error": {...}}`."""

    error: ErrorDetail


class PageParams(BaseModel):
    """Query-параметры для пагинации."""

    model_config = ConfigDict(extra="ignore")

    page: int = Field(default=1, ge=1, description="Номер страницы (с 1)")
    per_page: int = Field(
        default=20, ge=1, le=100, description="Размер страницы (1-100)"
    )
    sort: str | None = Field(
        default=None,
        description="Поле сортировки, префикс '-' для убывания (пример: '-created_at')",
    )

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page

    @property
    def limit(self) -> int:
        return self.per_page


class Pagination(BaseModel):
    """Метаинформация о странице в ответе."""

    page: int
    per_page: int
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)

    @classmethod
    def build(cls, *, page: int, per_page: int, total: int) -> Pagination:
        total_pages = (total + per_page - 1) // per_page if total else 0
        return cls(page=page, per_page=per_page, total=total, total_pages=total_pages)


class PaginatedResponse[T](BaseModel):
    """Унифицированная обёртка списковых ответов."""

    items: list[T]
    pagination: Pagination


class OkResponse(BaseModel):
    """Простой ответ `{ok: true}` для действий без payload."""

    ok: bool = True
