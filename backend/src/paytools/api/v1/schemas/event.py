"""Pydantic-схемы для событий: запросы, ответы."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from paytools.db.models.enums import EventStatus
from paytools.domain.events.validation import (
    CapacityPolicy,
    CustomFieldsSchema,
    Schedule,
)

# ---------------------------------------------------------------------------
# Вложенные схемы
# ---------------------------------------------------------------------------


class ScheduleResponse(BaseModel):
    """Расписание события (сериализация JSONB)."""

    type: str
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    sessions: list[dict[str, Any]] | None = None


class CapacityPolicyResponse(BaseModel):
    """Политика вместимости (сериализация JSONB)."""

    type: str
    limit: int | None = None
    total: int | None = None


# ---------------------------------------------------------------------------
# Organizer: создание / обновление
# ---------------------------------------------------------------------------


class EventCreateRequest(BaseModel):
    """Запрос на создание события."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255, description="Название события")
    slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$",
        description=(
            "Slug для URL (латиница, цифры, дефисы). "
            "Если не указан — генерируется из title."
        ),
    )
    description_md: str | None = Field(
        default=None, max_length=50000, description="Markdown-описание"
    )
    location_name: str | None = Field(
        default=None, max_length=255, description="Название места"
    )
    location_address: str | None = Field(
        default=None, max_length=1000, description="Адрес"
    )
    location_lat: float | None = Field(default=None, description="Широта")
    location_lng: float | None = Field(default=None, description="Долгота")
    schedule: Schedule = Field(description="Расписание события")
    capacity_policy: CapacityPolicy = Field(description="Политика вместимости")
    custom_fields_schema: CustomFieldsSchema = Field(
        default=None, description="Схема кастомных полей формы брони"
    )


class EventUpdateRequest(BaseModel):
    """PATCH-запрос на обновление события.

    Все поля опциональны — обновляются только переданные.
    """

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(
        default=None, min_length=1, max_length=255, description="Название"
    )
    description_md: str | None = Field(
        default=None, max_length=50000, description="Markdown-описание"
    )
    location_name: str | None = Field(
        default=None, max_length=255, description="Название места"
    )
    location_address: str | None = Field(
        default=None, max_length=1000, description="Адрес"
    )
    location_lat: float | None = Field(default=None, description="Широта")
    location_lng: float | None = Field(default=None, description="Долгота")
    schedule: Schedule | None = Field(default=None, description="Расписание")
    capacity_policy: CapacityPolicy | None = Field(
        default=None, description="Политика вместимости"
    )
    custom_fields_schema: CustomFieldsSchema | None = Field(
        default=None, description="Схема кастомных полей"
    )


# ---------------------------------------------------------------------------
# Organizer: ответы
# ---------------------------------------------------------------------------


class EventListItem(BaseModel):
    """Элемент списка событий (organizer view)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    title: str
    schedule: Any  # JSONB как есть
    status: EventStatus
    location_name: str | None = None
    image_card_url: str | None = None
    sold_count: int = 0
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    # Вычисляемые поля
    price_from_kopecks: int | None = Field(
        default=None,
        description="Минимальная цена среди активных тарифов",
    )
    is_sold_out: bool = Field(default=False, description="Все билеты проданы")


class EventDetailResponse(BaseModel):
    """Детальная информация о событии (organizer view)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    slug: str
    title: str
    description_md: str | None = None
    location_name: str | None = None
    location_address: str | None = None
    location_lat: float | None = None
    location_lng: float | None = None
    schedule: Any
    capacity_policy: Any
    sold_count: int = 0
    image_card_url: str | None = None
    image_background_url: str | None = None
    custom_fields_schema: Any | None = None
    status: EventStatus
    moderation_note: str | None = None
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    # Тарифы (список)
    tariffs: list[Any] = Field(
        default_factory=list, description="Список тарифов события"
    )


class EventCreateResponse(EventDetailResponse):
    """Ответ при создании события."""

    pass


# ---------------------------------------------------------------------------
# Public: ответы
# ---------------------------------------------------------------------------


class PublicEventListItem(BaseModel):
    """Элемент списка событий (публичная витрина)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    title: str
    schedule: Any
    location_name: str | None = None
    image_card_url: str | None = None
    price_from_kopecks: int | None = Field(
        default=None,
        description="Минимальная цена среди активных тарифов",
    )
    is_sold_out: bool = Field(default=False, description="Все билеты проданы")


class PublicEventDetailResponse(BaseModel):
    """Детальная информация о событии (публичная витрина).

    Включает только активные тарифы.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    title: str
    description_md: str | None = None
    location_name: str | None = None
    location_address: str | None = None
    schedule: Any
    image_card_url: str | None = None
    image_background_url: str | None = None
    custom_fields_schema: Any | None = None
    published_at: datetime | None = None
    price_from_kopecks: int | None = Field(
        default=None,
        description="Минимальная цена среди активных тарифов",
    )
    is_sold_out: bool = Field(default=False)
    tariffs: list[Any] = Field(
        default_factory=list, description="Активные тарифы события"
    )


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------


class AdminEventListItem(BaseModel):
    """Элемент списка событий на модерации (админ)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    slug: str
    title: str
    schedule: Any
    status: EventStatus
    location_name: str | None = None
    created_at: datetime
    updated_at: datetime


class RejectEventRequest(BaseModel):
    """Запрос на отклонение события."""

    model_config = ConfigDict(extra="forbid")

    note: str = Field(
        min_length=3,
        max_length=1000,
        description="Причина отклонения (отображается организатору)",
    )


# ---------------------------------------------------------------------------
# Хелперы для маппинга ORM → Pydantic
# ---------------------------------------------------------------------------


def _compute_price_from(event: Any) -> int | None:
    """Вычислить минимальную цену среди активных тарифов."""
    tariffs = getattr(event, "tariffs", []) or []
    active_tariffs = [t for t in tariffs if getattr(t, "is_active", False)]
    if not active_tariffs:
        return None
    prices = [int(getattr(t, "price_kopecks", 0)) for t in active_tariffs]
    return min(prices) if prices else None


def _compute_is_sold_out(event: Any) -> bool:
    """Проверить sold out на основе capacity_policy."""
    policy: dict[str, Any] = getattr(event, "capacity_policy", {}) or {}
    policy_type = policy.get("type", "unlimited")

    if policy_type == "unlimited":
        return False
    if policy_type in ("total", "hybrid"):
        limit: int = int(policy.get("limit") or policy.get("total", 0))
        sold: int = int(getattr(event, "sold_count", 0))
        return sold >= limit
    return False


def build_event_list_item(event: Any) -> EventListItem:
    """Смаппить ORM-событие в EventListItem."""
    return EventListItem(
        id=event.id,
        slug=event.slug,
        title=event.title,
        schedule=event.schedule,
        status=event.status,
        location_name=event.location_name,
        image_card_url=event.image_card_url,
        sold_count=event.sold_count,
        published_at=event.published_at,
        created_at=event.created_at,
        updated_at=event.updated_at,
        price_from_kopecks=_compute_price_from(event),
        is_sold_out=_compute_is_sold_out(event),
    )


def build_event_detail(event: Any, tariffs: list[Any]) -> EventDetailResponse:
    """Смаппить ORM-событие + тарифы в EventDetailResponse."""
    from paytools.api.v1.schemas.tariff import build_tariff_response

    return EventDetailResponse(
        id=event.id,
        organization_id=event.organization_id,
        slug=event.slug,
        title=event.title,
        description_md=event.description_md,
        location_name=event.location_name,
        location_address=event.location_address,
        location_lat=event.location_lat,
        location_lng=event.location_lng,
        schedule=event.schedule,
        capacity_policy=event.capacity_policy,
        sold_count=event.sold_count,
        image_card_url=event.image_card_url,
        image_background_url=event.image_background_url,
        custom_fields_schema=event.custom_fields_schema,
        status=event.status,
        moderation_note=event.moderation_note,
        published_at=event.published_at,
        created_at=event.created_at,
        updated_at=event.updated_at,
        tariffs=[build_tariff_response(t) for t in tariffs],
    )


def build_public_event_list_item(event: Any) -> PublicEventListItem:
    """Смаппить ORM-событие в PublicEventListItem."""
    return PublicEventListItem(
        id=event.id,
        slug=event.slug,
        title=event.title,
        schedule=event.schedule,
        location_name=event.location_name,
        image_card_url=event.image_card_url,
        price_from_kopecks=_compute_price_from(event),
        is_sold_out=_compute_is_sold_out(event),
    )


def build_public_event_detail(
    event: Any, tariffs: list[Any]
) -> PublicEventDetailResponse:
    """Смаппить ORM-событие + активные тарифы в PublicEventDetailResponse."""
    from paytools.api.v1.schemas.tariff import build_tariff_response

    return PublicEventDetailResponse(
        id=event.id,
        slug=event.slug,
        title=event.title,
        description_md=event.description_md,
        location_name=event.location_name,
        location_address=event.location_address,
        schedule=event.schedule,
        image_card_url=event.image_card_url,
        image_background_url=event.image_background_url,
        custom_fields_schema=event.custom_fields_schema,
        published_at=event.published_at,
        price_from_kopecks=_compute_price_from(event),
        is_sold_out=_compute_is_sold_out(event),
        tariffs=[build_tariff_response(t) for t in tariffs],
    )
