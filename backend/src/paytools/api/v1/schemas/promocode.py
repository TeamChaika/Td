"""Pydantic-схемы для промокодов."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from paytools.db.models.enums import DiscountType
from paytools.db.models.promocode import PromoCode, PromoCodeUsage


# --------------------------------------------------------------------------- #
# Запросы
# --------------------------------------------------------------------------- #


class PromoCodeCreateRequest(BaseModel):
    """Запрос на создание промокода."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=2, max_length=64)
    description: str | None = None
    discount_type: DiscountType
    discount_value: int = Field(ge=1, description="Значение скидки (в зависимости от типа)")
    event_id: UUID | None = None
    tariff_id: UUID | None = None
    usage_limit: int | None = Field(default=None, ge=1)
    per_user_limit: int | None = Field(default=None, ge=1)
    active_from: datetime | None = None
    active_to: datetime | None = None
    is_active: bool = True
    is_affiliate: bool = False
    affiliate_user_id: UUID | None = None


class PromoCodeUpdateRequest(BaseModel):
    """Запрос на обновление промокода (PATCH-семантика)."""

    model_config = ConfigDict(extra="forbid")

    description: str | None = None
    discount_type: DiscountType | None = None
    discount_value: int | None = Field(default=None, ge=1)
    event_id: UUID | None = None
    tariff_id: UUID | None = None
    usage_limit: int | None = Field(default=None, ge=1)
    per_user_limit: int | None = Field(default=None, ge=1)
    active_from: datetime | None = None
    active_to: datetime | None = None
    is_active: bool | None = None


class PromoCodeValidateItemRequest(BaseModel):
    """Элемент для расчёта скидки при валидации."""

    tariff_id: UUID
    quantity: int = Field(ge=1)


class PromoCodeValidateRequest(BaseModel):
    """Запрос на валидацию промокода (публичный)."""

    code: str = Field(min_length=2, max_length=64)
    event_id: UUID
    email: str
    items: list[PromoCodeValidateItemRequest]


# --------------------------------------------------------------------------- #
# Ответы
# --------------------------------------------------------------------------- #


class PromoCodeResponse(BaseModel):
    """Ответ промокода для организатора."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    description: str | None
    discount_type: DiscountType
    discount_value: int
    event_id: UUID | None
    tariff_id: UUID | None
    usage_limit: int | None
    used_count: int
    per_user_limit: int | None
    active_from: datetime | None
    active_to: datetime | None
    is_active: bool
    is_affiliate: bool
    affiliate_user_id: UUID | None
    created_at: datetime


class PromoCodeValidateResponse(BaseModel):
    """Ответ на валидацию промокода."""

    valid: bool
    code: str = ""
    discount_type: DiscountType | None = None
    discount_value: int = 0
    discount_kopecks: int = 0
    description: str = ""
    error_code: str | None = None
    error_message: str | None = None


class PromoCodeUsageResponse(BaseModel):
    """Факт использования промокода."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    promo_code_id: UUID
    reservation_id: UUID
    email: str
    discount_kopecks: int
    created_at: datetime


# --------------------------------------------------------------------------- #
# Builder-функции
# --------------------------------------------------------------------------- #


def build_promo_code_response(p: PromoCode) -> PromoCodeResponse:
    """Собрать PromoCodeResponse из ORM-модели."""
    return PromoCodeResponse(
        id=p.id,
        code=p.code,
        description=p.description,
        discount_type=p.discount_type,
        discount_value=p.discount_value,
        event_id=p.event_id,
        tariff_id=p.tariff_id,
        usage_limit=p.usage_limit,
        used_count=p.used_count,
        per_user_limit=p.per_user_limit,
        active_from=p.active_from,
        active_to=p.active_to,
        is_active=p.is_active,
        is_affiliate=p.is_affiliate,
        affiliate_user_id=p.affiliate_user_id,
        created_at=p.created_at,
    )


def build_promo_usage_response(u: PromoCodeUsage) -> PromoCodeUsageResponse:
    """Собрать PromoCodeUsageResponse из ORM-модели."""
    return PromoCodeUsageResponse(
        id=u.id,
        promo_code_id=u.promo_code_id,
        reservation_id=u.reservation_id,
        email=u.email,
        discount_kopecks=u.discount_kopecks,
        created_at=u.created_at,
    )
