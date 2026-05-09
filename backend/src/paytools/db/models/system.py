"""Системные таблицы: webhook deliveries, audit log, email blocklist."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from paytools.db.base import Base
from paytools.db.mixins import UUIDPkMixin


class WebhookDelivery(UUIDPkMixin, Base):
    """Сырой лог приходящих webhook-ов от платёжных провайдеров."""

    __tablename__ = "webhook_deliveries"

    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str | None] = mapped_column(String(64))

    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    headers: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    signature_valid: Mapped[bool | None] = mapped_column(Boolean)
    processed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    processing_error: Mapped[str | None] = mapped_column(Text)

    related_payment_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="RESTRICT"),
    )

    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class AuditLog(UUIDPkMixin, Base):
    """Лог критичных действий (approve/suspend, refund, qrm_key update, etc.)."""

    __tablename__ = "audit_log"

    organization_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        index=True,
    )
    user_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
    )

    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(64))
    resource_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))

    # Структура: {"before": {...}, "after": {...}} или произвольная
    data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    ip: Mapped[str | None] = mapped_column(INET)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (Index("ix_audit_log_created", "created_at"),)


class EmailBlocklist(Base):
    """Список доменов disposable-почты.

    Первичный ключ — сам домен (lower-case), отдельной `id` не держим.
    """

    __tablename__ = "email_blocklist"

    domain: Mapped[str] = mapped_column(String(255), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(
        String(64), default="manual", server_default="manual", nullable=False
    )
