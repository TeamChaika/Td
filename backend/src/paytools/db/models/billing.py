"""Биллинг-кошелёк организации и транзакции комиссии."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import BigInteger, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from paytools.db.base import Base
from paytools.db.mixins import TimestampsMixin, UUIDPkMixin
from paytools.db.models.enums import (
    BalanceTransactionType,
    balance_transaction_type_enum,
)

if TYPE_CHECKING:
    from paytools.db.models.organization import Organization


class OrganizationBalance(TimestampsMixin, Base):
    """Баланс-кошелёк организации (одна запись на организацию).

    Может быть отрицательным (задолженность перед платформой).
    """

    __tablename__ = "organization_balance"

    organization_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        primary_key=True,
    )

    balance_kopecks: Mapped[int] = mapped_column(
        BigInteger, default=0, server_default="0", nullable=False
    )

    organization: Mapped[Organization] = relationship(back_populates="balance")


class BalanceTransaction(UUIDPkMixin, TimestampsMixin, Base):
    """Движение по биллинг-счёту организации."""

    __tablename__ = "balance_transactions"

    organization_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    type: Mapped[BalanceTransactionType] = mapped_column(
        balance_transaction_type_enum, nullable=False
    )
    amount_kopecks: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance_after_kopecks: Mapped[int] = mapped_column(BigInteger, nullable=False)

    related_payment_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="RESTRICT"),
    )
    description: Mapped[str | None] = mapped_column(Text)

    created_by_user_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
    )

    __table_args__ = (
        Index(
            "ix_balance_tx_org_created",
            "organization_id",
            "created_at",
        ),
    )
