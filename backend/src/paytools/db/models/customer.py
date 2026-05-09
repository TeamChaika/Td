"""Модель Customer — покупатель с ЛК (активно используется с v1.0)."""

from __future__ import annotations

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from paytools.db.base import Base
from paytools.db.mixins import TimestampsMixin, UUIDPkMixin


class Customer(UUIDPkMixin, TimestampsMixin, Base):
    """Покупатель. В MVP создаётся опционально (guest checkout основной сценарий)."""

    __tablename__ = "customers"

    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(32), index=True)
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True)
