from __future__ import annotations

from datetime import datetime
from uuid import UUID

import uuid_utils
from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column


def _uuid7() -> UUID:
    """Генерация UUIDv7 (сортируется по времени)."""
    return UUID(bytes=bytes(uuid_utils.uuid7().bytes))


class UUIDPkMixin:
    """Миксин с UUID v7 PK."""

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        default=_uuid7,
    )


class TimestampsMixin:
    """Миксин с created_at/updated_at (TIMESTAMPTZ UTC)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class TenantMixin:
    """Миксин с organization_id (для всех бизнес-таблиц)."""

    organization_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
