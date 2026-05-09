"""Pydantic-схемы для тарифов: запросы, ответы."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Organizer: создание / обновление
# ---------------------------------------------------------------------------


class TariffCreateRequest(BaseModel):
    """Запрос на создание тарифа."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255, description="Название тарифа")
    description: str | None = Field(
        default=None, max_length=5000, description="Описание тарифа"
    )
    price_kopecks: int = Field(
        ge=0, description="Цена в копейках (0 для complimentary)"
    )
    capacity_limit: int | None = Field(
        default=None, ge=0, description="Лимит билетов по тарифу (null = безлимит)"
    )
    is_complimentary: bool = Field(
        default=False, description="Приглашённый тариф (бесплатный, создаётся админом)"
    )
    sort_order: int = Field(default=0, ge=0, description="Порядок сортировки")
    is_active: bool = Field(default=True, description="Тариф активен")


class TariffUpdateRequest(BaseModel):
    """PATCH-запрос на обновление тарифа."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(
        default=None, min_length=1, max_length=255, description="Название"
    )
    description: str | None = Field(
        default=None, max_length=5000, description="Описание"
    )
    price_kopecks: int | None = Field(default=None, ge=0, description="Цена в копейках")
    capacity_limit: int | None = Field(default=None, ge=0, description="Лимит билетов")
    is_complimentary: bool | None = Field(
        default=None, description="Приглашённый тариф"
    )
    sort_order: int | None = Field(default=None, ge=0, description="Порядок сортировки")
    is_active: bool | None = Field(default=None, description="Тариф активен")


# ---------------------------------------------------------------------------
# Ответы
# ---------------------------------------------------------------------------


class TariffResponse(BaseModel):
    """Тариф в ответе API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID
    name: str
    description: str | None = None
    price_kopecks: int
    capacity_limit: int | None = None
    sold_count: int = 0
    is_complimentary: bool = False
    sort_order: int = 0
    is_active: bool = True
    created_at: datetime | None = None  # datetime из БД


class TariffDeleteResponse(BaseModel):
    """Ответ при удалении тарифа."""

    deleted: bool = True
    method: str = Field(description="'hard' или 'soft' (деактивация)")
    tariff_id: UUID


# ---------------------------------------------------------------------------
# Хелперы
# ---------------------------------------------------------------------------


def build_tariff_response(tariff: Any) -> dict[str, Any]:
    """Смаппить ORM-тариф в словарь для Pydantic-схем.

    Используется в build_event_detail, build_public_event_detail.
    """
    return {
        "id": tariff.id,
        "event_id": tariff.event_id,
        "name": tariff.name,
        "description": tariff.description,
        "price_kopecks": tariff.price_kopecks,
        "capacity_limit": tariff.capacity_limit,
        "sold_count": tariff.sold_count,
        "is_complimentary": tariff.is_complimentary,
        "sort_order": tariff.sort_order,
        "is_active": tariff.is_active,
        "created_at": tariff.created_at,
    }
