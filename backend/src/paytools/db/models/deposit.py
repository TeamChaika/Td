"""Депозиты (v1.1).

Схема готова в MVP для будущего расширения. В Phase 1-6 записи
в этих таблицах не создаются.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from paytools.db.base import Base
from paytools.db.mixins import TenantMixin, TimestampsMixin, UUIDPkMixin
from paytools.db.models.enums import (
    DepositStatus,
    DepositTransactionType,
    deposit_status_enum,
    deposit_transaction_type_enum,
)


class Deposit(UUIDPkMixin, TimestampsMixin, TenantMixin, Base):
    """Депозит стола/заказа, привязанный к билету (v1.1)."""

    __tablename__ = "deposits"

    ticket_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("tickets.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    reservation_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("reservations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    table_number: Mapped[str | None] = mapped_column(String(32))

    initial_amount_kopecks: Mapped[int] = mapped_column(BigInteger, nullable=False)
    remaining_amount_kopecks: Mapped[int] = mapped_column(BigInteger, nullable=False)

    payment_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="RESTRICT"),
    )

    status: Mapped[DepositStatus] = mapped_column(
        deposit_status_enum,
        default=DepositStatus.PENDING_PAYMENT,
        server_default=DepositStatus.PENDING_PAYMENT.value,
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Флаг "внёс ли админ в iiko" — для MVP это ручное действие
    synced_to_iiko: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    iiko_order_id: Mapped[str | None] = mapped_column(String(128))


class DepositTransaction(UUIDPkMixin, TimestampsMixin, Base):
    """Движение по депозиту (списание/возврат/корректировка)."""

    __tablename__ = "deposit_transactions"

    deposit_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("deposits.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    amount_kopecks: Mapped[int] = mapped_column(BigInteger, nullable=False)
    type: Mapped[DepositTransactionType] = mapped_column(
        deposit_transaction_type_enum, nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text)

    created_by_user_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
    )
