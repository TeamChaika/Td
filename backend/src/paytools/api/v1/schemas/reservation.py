"""Pydantic-схемы для бронирований."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from paytools.db.models.enums import ReservationStatus
from paytools.db.models.reservation import Reservation, ReservationItem


# --------------------------------------------------------------------------- #
# Запросы
# --------------------------------------------------------------------------- #


class ReservationItemRequest(BaseModel):
    """Элемент бронирования в запросе."""

    tariff_id: UUID
    quantity: int = Field(ge=1, le=50)


class CreateReservationRequest(BaseModel):
    """Запрос на создание бронирования."""

    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    session_id: UUID | None = None
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone: str = Field(min_length=10, max_length=32)
    items: list[ReservationItemRequest] = Field(min_length=1)
    custom_fields: dict[str, object] | None = None
    promo_code: str | None = Field(default=None, max_length=64)
    referrer_code: str | None = Field(default=None, max_length=64)
    consent_privacy: bool
    consent_offer: bool


class CancelReservationRequest(BaseModel):
    """Запрос на отмену бронирования."""

    reason: str | None = Field(default=None, max_length=500)


# --------------------------------------------------------------------------- #
# Ответы
# --------------------------------------------------------------------------- #


class ReservationItemResponse(BaseModel):
    """Элемент бронирования в ответе."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tariff_id: UUID
    quantity: int
    price_kopecks: int
    subtotal_kopecks: int


class ReservationResponse(BaseModel):
    """Полный ответ бронирования."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID
    status: ReservationStatus
    first_name: str
    last_name: str
    email: str
    phone: str
    items_subtotal_kopecks: int
    discount_kopecks: int
    total_kopecks: int
    promo_code_id: UUID | None
    expires_at: datetime | None
    paid_at: datetime | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    created_at: datetime
    items: list[ReservationItemResponse] = []


class ReservationCreateResponse(BaseModel):
    """Краткий ответ при создании бронирования."""

    id: UUID
    status: ReservationStatus
    total_kopecks: int
    discount_kopecks: int
    expires_at: datetime | None
    payment_url: str


class ReservationListItem(BaseModel):
    """Элемент списка бронирований для организатора."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID
    status: ReservationStatus
    first_name: str
    last_name: str
    email: str
    phone: str
    total_kopecks: int
    discount_kopecks: int
    created_at: datetime
    expires_at: datetime | None
    paid_at: datetime | None


# --------------------------------------------------------------------------- #
# Builder-функции
# --------------------------------------------------------------------------- #


def build_reservation_response(r: Reservation) -> ReservationResponse:
    """Собрать ReservationResponse из ORM-модели."""
    items = [
        ReservationItemResponse(
            id=item.id,
            tariff_id=item.tariff_id,
            quantity=item.quantity,
            price_kopecks=item.price_kopecks,
            subtotal_kopecks=item.subtotal_kopecks,
        )
        for item in (r.items or [])
    ]
    return ReservationResponse(
        id=r.id,
        event_id=r.event_id,
        status=r.status,
        first_name=r.first_name,
        last_name=r.last_name,
        email=r.email,
        phone=r.phone,
        items_subtotal_kopecks=r.items_subtotal_kopecks,
        discount_kopecks=r.discount_kopecks,
        total_kopecks=r.total_kopecks,
        promo_code_id=r.promo_code_id,
        expires_at=r.expires_at,
        paid_at=r.paid_at,
        cancelled_at=r.cancelled_at,
        cancel_reason=r.cancel_reason,
        created_at=r.created_at,
        items=items,
    )


def build_reservation_list_item(r: Reservation) -> ReservationListItem:
    """Собрать ReservationListItem из ORM-модели."""
    return ReservationListItem(
        id=r.id,
        event_id=r.event_id,
        status=r.status,
        first_name=r.first_name,
        last_name=r.last_name,
        email=r.email,
        phone=r.phone,
        total_kopecks=r.total_kopecks,
        discount_kopecks=r.discount_kopecks,
        created_at=r.created_at,
        expires_at=r.expires_at,
        paid_at=r.paid_at,
    )


def build_reservation_create_response(r: Reservation) -> ReservationCreateResponse:
    """Собрать ReservationCreateResponse из ORM-модели."""
    return ReservationCreateResponse(
        id=r.id,
        status=r.status,
        total_kopecks=r.total_kopecks,
        discount_kopecks=r.discount_kopecks,
        expires_at=r.expires_at,
        payment_url=f"/pay/{r.id}",
    )
