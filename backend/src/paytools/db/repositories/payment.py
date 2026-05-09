"""Репозиторий для работы с платежами (Payment)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from paytools.db.models.enums import PaymentStatus
from paytools.db.models.payment import Payment
from paytools.db.repositories.base import BaseRepository


class PaymentRepository(BaseRepository[Payment]):
    """Репозиторий платежей."""

    model = Payment

    async def get_by_reservation(self, reservation_id: UUID) -> Payment | None:
        """Найти платёж по reservation_id (последний созданный)."""
        stmt = (
            select(Payment)
            .where(Payment.reservation_id == reservation_id)
            .order_by(Payment.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_provider_payment_id(
        self, provider_payment_id: str
    ) -> Payment | None:
        """Найти платёж по ID в платёжной системе (QRM invoice_id)."""
        stmt = select(Payment).where(
            Payment.provider_payment_id == provider_payment_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, **data: Any) -> Payment:
        """Создать платёж."""
        payment = Payment(**data)
        self.session.add(payment)
        await self.session.flush()
        return payment

    async def find_expired_pending(self, now: datetime) -> list[Payment]:
        """Найти все pending платежи с истёкшим сроком."""
        stmt = select(Payment).where(
            Payment.status == PaymentStatus.PENDING,
            Payment.expires_at < now,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_reservation(self, reservation_id: UUID) -> int:
        """Количество платёжных попыток по бронированию."""
        stmt = (
            select(func.count())
            .select_from(Payment)
            .where(Payment.reservation_id == reservation_id)
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one())
