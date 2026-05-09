"""Модель Organization — арендатор (организатор мероприятий)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, Boolean, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from paytools.db.base import Base
from paytools.db.mixins import TimestampsMixin, UUIDPkMixin
from paytools.db.models.enums import (
    OrganizationStatus,
    legal_entity_type_enum,
    organization_status_enum,
)

if TYPE_CHECKING:
    from paytools.db.models.billing import OrganizationBalance
    from paytools.db.models.event import Event
    from paytools.db.models.user import User


class Organization(UUIDPkMixin, TimestampsMixin, Base):
    """Организатор мероприятий. Верхний уровень multi-tenancy."""

    __tablename__ = "organizations"

    # --- Идентификация ---
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    brand_name: Mapped[str | None] = mapped_column(String(255))

    # --- Брендинг ---
    logo_url: Mapped[str | None] = mapped_column(Text)
    brand_color: Mapped[str | None] = mapped_column(String(7))  # #RRGGBB

    # --- Публичные контакты ---
    contact_email: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(32))

    # --- Юридические реквизиты (для оферты) ---
    legal_entity_type: Mapped[str | None] = mapped_column(legal_entity_type_enum)
    legal_inn: Mapped[str | None] = mapped_column(String(12))
    legal_name: Mapped[str | None] = mapped_column(String(255))
    legal_address: Mapped[str | None] = mapped_column(Text)

    # --- QR Manager (зашифрованный ключ) ---
    qrm_api_key_encrypted: Mapped[str | None] = mapped_column(Text)
    qrm_api_login: Mapped[str | None] = mapped_column(String(255))
    qrm_prod_mode: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )

    # --- White-label (v1.1) ---
    custom_domain: Mapped[str | None] = mapped_column(String(255), unique=True)
    white_label_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )

    # --- Кастомный SMTP организатора (опционально) ---
    smtp_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # --- Telegram-уведомления ---
    # BigInteger — у telegram chat id может быть большое отрицательное значение
    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger)

    # --- Политики ---
    refund_policy: Mapped[str | None] = mapped_column(Text)
    auto_publish_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )

    # --- Статус ---
    status: Mapped[OrganizationStatus] = mapped_column(
        organization_status_enum,
        default=OrganizationStatus.PENDING_MODERATION,
        server_default=OrganizationStatus.PENDING_MODERATION.value,
        nullable=False,
    )

    # --- Geo (на будущее для отображения на карте) ---
    timezone: Mapped[str] = mapped_column(
        String(64),
        default="Europe/Moscow",
        server_default="Europe/Moscow",
        nullable=False,
    )

    # --- Связи ---
    events: Mapped[list[Event]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    users: Mapped[list[User]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    balance: Mapped[OrganizationBalance | None] = relationship(
        back_populates="organization", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_organizations_status", "status"),)
