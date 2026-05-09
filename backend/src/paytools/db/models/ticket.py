"""Модель Ticket — выпущенный билет."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from paytools.db.base import Base
from paytools.db.mixins import TenantMixin, TimestampsMixin, UUIDPkMixin
from paytools.db.models.enums import TicketStatus, ticket_status_enum

if TYPE_CHECKING:
    from paytools.db.models.reservation import Reservation


class Ticket(UUIDPkMixin, TimestampsMixin, TenantMixin, Base):
    """Билет (1 штука = 1 проход).

    `code` — короткий человекочитаемый код для ручного ввода сканером
    (например, `ABCD-1234`). `qr_payload` — строка для QR-кода,
    подписана HMAC на сервере.
    """

    __tablename__ = "tickets"

    event_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("events.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    reservation_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("reservations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    tariff_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("tariffs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reservation_item_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("reservation_items.id", ondelete="RESTRICT"),
        nullable=False,
    )

    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    qr_payload: Mapped[str] = mapped_column(Text, nullable=False)

    guest_first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    guest_last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    guest_index: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    status: Mapped[TicketStatus] = mapped_column(
        ticket_status_enum,
        default=TicketStatus.ISSUED,
        server_default=TicketStatus.ISSUED.value,
        nullable=False,
    )
    is_complimentary: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )

    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checked_in_by_user_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
    )

    pdf_url: Mapped[str | None] = mapped_column(Text)

    # --- Связи ---
    reservation: Mapped[Reservation] = relationship(back_populates="tickets")

    __table_args__ = (
        Index("ix_tickets_org_event_status", "organization_id", "event_id", "status"),
    )
