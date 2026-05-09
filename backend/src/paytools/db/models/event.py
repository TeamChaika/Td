"""Модели Event и Tariff."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from paytools.db.base import Base
from paytools.db.mixins import TenantMixin, TimestampsMixin, UUIDPkMixin
from paytools.db.models.enums import EventStatus, event_status_enum

if TYPE_CHECKING:
    from paytools.db.models.organization import Organization


class Event(UUIDPkMixin, TimestampsMixin, TenantMixin, Base):
    """Мероприятие.

    `schedule` — JSONB с discriminated union по `type`:
      - {"type": "single", "starts_at": ISO, "ends_at": ISO}
      - {"type": "sessions", "sessions": [{...}, ...]}
      - {"type": "period", "starts_at": ISO, "ends_at": ISO}

    `capacity_policy` — JSONB:
      - {"type": "total", "limit": int}
      - {"type": "per_tariff"}   (лимиты в tariffs.capacity_limit)
      - {"type": "hybrid", "total": int}
      - {"type": "unlimited"}

    `custom_fields_schema` — список описаний кастомных полей формы брони.
    """

    __tablename__ = "events"

    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description_md: Mapped[str | None] = mapped_column(Text)

    location_name: Mapped[str | None] = mapped_column(String(255))
    location_address: Mapped[str | None] = mapped_column(Text)
    # Координаты храним как два float'а (без PostGIS-зависимости)
    location_lat: Mapped[float | None] = mapped_column(Float)
    location_lng: Mapped[float | None] = mapped_column(Float)

    schedule: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    capacity_policy: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    sold_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )

    image_card_url: Mapped[str | None] = mapped_column(Text)
    image_background_url: Mapped[str | None] = mapped_column(Text)

    custom_fields_schema: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)

    status: Mapped[EventStatus] = mapped_column(
        event_status_enum,
        default=EventStatus.DRAFT,
        server_default=EventStatus.DRAFT.value,
        nullable=False,
    )
    moderation_note: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # --- Связи ---
    organization: Mapped[Organization] = relationship(back_populates="events")
    tariffs: Mapped[list[Tariff]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
        order_by="Tariff.sort_order",
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_events_org_slug"),
        Index("ix_events_org_status", "organization_id", "status"),
        Index("ix_events_published_at", "published_at"),
    )


class Tariff(UUIDPkMixin, TimestampsMixin, TenantMixin, Base):
    """Тариф (тип билета) на событие."""

    __tablename__ = "tariffs"

    event_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("events.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    # Цена в копейках
    price_kopecks: Mapped[int] = mapped_column(BigInteger, nullable=False)

    capacity_limit: Mapped[int | None] = mapped_column(Integer)
    sold_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )

    is_complimentary: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )

    sort_order: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )

    # --- Связи ---
    event: Mapped[Event] = relationship(back_populates="tariffs")
