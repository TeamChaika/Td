"""Модели PromoCode и PromoCodeUsage."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from paytools.db.base import Base
from paytools.db.mixins import TenantMixin, TimestampsMixin, UUIDPkMixin
from paytools.db.models.enums import DiscountType, discount_type_enum


class PromoCode(UUIDPkMixin, TimestampsMixin, TenantMixin, Base):
    """Промокод на скидку.

    `discount_value` хранится:
      - для PERCENT — значение × 100 (1500 = 15%)
      - для FIXED_AMOUNT — сумма в копейках (скидка)
      - для FIXED_PRICE — итоговая цена билета в копейках
    """

    __tablename__ = "promo_codes"

    # Код хранится upper-case, сравнение case-insensitive на уровне сервиса
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    discount_type: Mapped[DiscountType] = mapped_column(
        discount_type_enum, nullable=False
    )
    discount_value: Mapped[int] = mapped_column(BigInteger, nullable=False)

    event_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("events.id", ondelete="RESTRICT"),
        index=True,
    )
    tariff_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("tariffs.id", ondelete="RESTRICT"),
    )

    usage_limit: Mapped[int | None] = mapped_column(Integer)
    used_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    per_user_limit: Mapped[int | None] = mapped_column(Integer)

    active_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )

    is_affiliate: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    affiliate_user_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_promo_codes_org_code"),
        Index("ix_promo_codes_org_active", "organization_id", "is_active"),
    )


class PromoCodeUsage(UUIDPkMixin, TimestampsMixin, Base):
    """Факт применения промокода (для enforcement per_user_limit)."""

    __tablename__ = "promo_code_usages"

    promo_code_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("promo_codes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reservation_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("reservations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    discount_kopecks: Mapped[int] = mapped_column(BigInteger, nullable=False)

    __table_args__ = (Index("ix_promo_usages_code_email", "promo_code_id", "email"),)
