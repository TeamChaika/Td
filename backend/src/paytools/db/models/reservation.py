"""Модели Reservation и ReservationItem."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from paytools.db.base import Base
from paytools.db.mixins import TenantMixin, TimestampsMixin, UUIDPkMixin
from paytools.db.models.enums import ReservationStatus, reservation_status_enum

if TYPE_CHECKING:
    from paytools.db.models.ticket import Ticket


class Reservation(UUIDPkMixin, TimestampsMixin, TenantMixin, Base):
    """Бронь (намерение купить). После оплаты преобразуется в Tickets."""

    __tablename__ = "reservations"

    event_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("events.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    customer_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        index=True,
    )
    # Если событие с расписанием sessions — фиксируем конкретный сеанс
    session_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))

    # --- Данные гостя ---
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)

    custom_fields_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # --- Суммы в копейках ---
    items_subtotal_kopecks: Mapped[int] = mapped_column(BigInteger, nullable=False)
    discount_kopecks: Mapped[int] = mapped_column(
        BigInteger, default=0, server_default="0", nullable=False
    )
    total_kopecks: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # --- Промокод / партнёр ---
    promo_code_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("promo_codes.id", ondelete="RESTRICT"),
    )
    referrer_code: Mapped[str | None] = mapped_column(String(64))

    # --- Жизненный цикл ---
    status: Mapped[ReservationStatus] = mapped_column(
        reservation_status_enum,
        default=ReservationStatus.DRAFT,
        server_default=ReservationStatus.DRAFT.value,
        nullable=False,
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(Text)

    # --- Техническое ---
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True)

    consent_privacy: Mapped[bool] = mapped_column(Boolean, nullable=False)
    consent_offer: Mapped[bool] = mapped_column(Boolean, nullable=False)

    user_agent: Mapped[str | None] = mapped_column(Text)
    ip: Mapped[str | None] = mapped_column(INET)

    # --- Связи ---
    items: Mapped[list[ReservationItem]] = relationship(
        back_populates="reservation", cascade="all, delete-orphan"
    )
    tickets: Mapped[list[Ticket]] = relationship(back_populates="reservation")

    __table_args__ = (
        Index("ix_reservations_org_status", "organization_id", "status"),
        Index("ix_reservations_event_status", "event_id", "status"),
        Index(
            "ix_reservations_status_expires",
            "status",
            "expires_at",
        ),
    )


class ReservationItem(UUIDPkMixin, TimestampsMixin, Base):
    """Строка брони: сколько билетов какого тарифа."""

    __tablename__ = "reservation_items"

    reservation_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("reservations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tariff_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("tariffs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    # Фиксируем цену на момент брони (тариф может менять цену)
    price_kopecks: Mapped[int] = mapped_column(BigInteger, nullable=False)
    subtotal_kopecks: Mapped[int] = mapped_column(BigInteger, nullable=False)

    reservation: Mapped[Reservation] = relationship(back_populates="items")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_reservation_items_qty_positive"),
    )
