"""Модель User — сотрудник платформы или организации."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from paytools.db.base import Base
from paytools.db.mixins import TimestampsMixin, UUIDPkMixin
from paytools.db.models.enums import UserRole, user_role_enum

if TYPE_CHECKING:
    from paytools.db.models.organization import Organization


class User(UUIDPkMixin, TimestampsMixin, Base):
    """Пользователь админки (superadmin / organizer / scanner / cashier / support)."""

    __tablename__ = "users"

    # Nullable — superadmin платформы не привязан к организации
    organization_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    # Nullable: может отсутствовать, если пользователь входит только через Telegram
    password_hash: Mapped[str | None] = mapped_column(Text)

    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(32))

    role: Mapped[UserRole] = mapped_column(user_role_enum, nullable=False)

    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    telegram_username: Mapped[str | None] = mapped_column(String(64))

    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # --- Связи ---
    organization: Mapped[Organization | None] = relationship(
        back_populates="users",
    )
