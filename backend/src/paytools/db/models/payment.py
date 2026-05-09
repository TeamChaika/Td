"""Модель Payment."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from paytools.db.base import Base
from paytools.db.mixins import TenantMixin, TimestampsMixin, UUIDPkMixin
from paytools.db.models.enums import (
    PaymentProviderType,
    PaymentStatus,
    payment_provider_enum,
    payment_status_enum,
)


class Payment(UUIDPkMixin, TimestampsMixin, TenantMixin, Base):
    """Платёж через провайдера (QRM / complimentary / cash)."""

    __tablename__ = "payments"

    reservation_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("reservations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    provider: Mapped[PaymentProviderType] = mapped_column(
        payment_provider_enum, nullable=False
    )
    provider_payment_id: Mapped[str | None] = mapped_column(String(128), index=True)

    amount_kopecks: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3), default="RUB", server_default="RUB", nullable=False
    )

    status: Mapped[PaymentStatus] = mapped_column(
        payment_status_enum,
        default=PaymentStatus.PENDING,
        server_default=PaymentStatus.PENDING.value,
        nullable=False,
        index=True,
    )

    qr_url: Mapped[str | None] = mapped_column(Text)
    qr_image_url: Mapped[str | None] = mapped_column(Text)

    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refunded_amount_kopecks: Mapped[int] = mapped_column(
        BigInteger, default=0, server_default="0", nullable=False
    )

    provider_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # Список событий от провайдера (webhook-ов), накапливаем историю
    webhook_events: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)

    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True)

    __table_args__ = (
        Index("ix_payments_provider_payment", "provider", "provider_payment_id"),
    )
