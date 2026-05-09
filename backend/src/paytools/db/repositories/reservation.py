"""Репозиторий для работы с бронированиями (Reservation, ReservationItem)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text, update
from sqlalchemy.orm import selectinload

from paytools.db.models.enums import ReservationStatus
from paytools.db.models.event import Event, Tariff
from paytools.db.models.reservation import Reservation, ReservationItem
from paytools.db.repositories.base import BaseRepository


class ReservationRepository(BaseRepository[Reservation]):
    """Репозиторий бронирований с поддержкой атомарной проверки capacity."""

    model = Reservation

    async def get_with_items(self, reservation_id: UUID) -> Reservation | None:
        """Загрузить бронь с eager-loading items."""
        stmt = (
            select(Reservation)
            .options(selectinload(Reservation.items))
            .where(Reservation.id == reservation_id)
        )
        stmt = self._apply_tenant_filter(stmt)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_idempotency_key(
        self, idempotency_key: str
    ) -> Reservation | None:
        """Найти бронь по idempotency_key (для повторных запросов)."""
        stmt = (
            select(Reservation)
            .options(selectinload(Reservation.items))
            .where(Reservation.idempotency_key == idempotency_key)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_reservation(
        self, **data: Any
    ) -> Reservation:
        """Создать бронь."""
        reservation = Reservation(**data)
        self.session.add(reservation)
        await self.session.flush()
        return reservation

    async def create_item(self, **data: Any) -> ReservationItem:
        """Создать строку брони."""
        item = ReservationItem(**data)
        self.session.add(item)
        await self.session.flush()
        return item

    # --- Атомарная проверка capacity ---

    async def atomic_increment_event_sold(
        self, event_id: UUID, qty: int, capacity_limit: int
    ) -> bool:
        """Атомарно увеличить sold_count события.

        Возвращает True если успешно (есть место), False если sold out.
        SQL: UPDATE events SET sold_count = sold_count + :qty
             WHERE id = :id AND sold_count + :qty <= :limit
        """
        stmt = (
            update(Event)
            .where(
                Event.id == event_id,
                Event.sold_count + qty <= capacity_limit,
            )
            .values(sold_count=Event.sold_count + qty)
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0  # type: ignore[union-attr]

    async def atomic_increment_tariff_sold(
        self, tariff_id: UUID, qty: int
    ) -> bool:
        """Атомарно увеличить sold_count тарифа.

        Если capacity_limit IS NULL — всегда успех (безлимитный).
        Иначе проверяем sold_count + qty <= capacity_limit.
        """
        stmt = (
            update(Tariff)
            .where(
                Tariff.id == tariff_id,
                # NULL capacity_limit = безлимитный тариф
                (Tariff.capacity_limit.is_(None))
                | (Tariff.sold_count + qty <= Tariff.capacity_limit),
            )
            .values(sold_count=Tariff.sold_count + qty)
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0  # type: ignore[union-attr]

    async def atomic_decrement_event_sold(
        self, event_id: UUID, qty: int
    ) -> None:
        """Компенсация: уменьшить sold_count события."""
        stmt = (
            update(Event)
            .where(Event.id == event_id)
            .values(sold_count=func.greatest(Event.sold_count - qty, 0))
        )
        await self.session.execute(stmt)

    async def atomic_decrement_tariff_sold(
        self, tariff_id: UUID, qty: int
    ) -> None:
        """Компенсация: уменьшить sold_count тарифа."""
        stmt = (
            update(Tariff)
            .where(Tariff.id == tariff_id)
            .values(sold_count=func.greatest(Tariff.sold_count - qty, 0))
        )
        await self.session.execute(stmt)

    # --- Expiration ---

    async def find_expired_pending(
        self, now: datetime
    ) -> list[Reservation]:
        """Найти все pending_payment брони с истёкшим сроком."""
        stmt = (
            select(Reservation)
            .options(selectinload(Reservation.items))
            .where(
                Reservation.status == ReservationStatus.PENDING_PAYMENT,
                Reservation.expires_at < now,
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # --- Списки для организатора ---

    async def list_for_organizer(
        self,
        org_id: UUID,
        *,
        event_id: UUID | None = None,
        status_filter: ReservationStatus | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Reservation]:
        """Список бронирований организации с фильтрами."""
        stmt = (
            select(Reservation)
            .options(selectinload(Reservation.items))
            .where(Reservation.organization_id == org_id)
        )
        if event_id is not None:
            stmt = stmt.where(Reservation.event_id == event_id)
        if status_filter is not None:
            stmt = stmt.where(Reservation.status == status_filter)
        if from_date is not None:
            stmt = stmt.where(Reservation.created_at >= from_date)
        if to_date is not None:
            stmt = stmt.where(Reservation.created_at <= to_date)

        stmt = stmt.order_by(Reservation.created_at.desc())
        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_for_organizer(
        self,
        org_id: UUID,
        *,
        event_id: UUID | None = None,
        status_filter: ReservationStatus | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> int:
        """Подсчёт бронирований организации."""
        stmt = (
            select(func.count())
            .select_from(Reservation)
            .where(Reservation.organization_id == org_id)
        )
        if event_id is not None:
            stmt = stmt.where(Reservation.event_id == event_id)
        if status_filter is not None:
            stmt = stmt.where(Reservation.status == status_filter)
        if from_date is not None:
            stmt = stmt.where(Reservation.created_at >= from_date)
        if to_date is not None:
            stmt = stmt.where(Reservation.created_at <= to_date)

        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def find_by_event_and_status(
        self,
        event_id: UUID,
        status: ReservationStatus,
    ) -> list[Reservation]:
        """Найти бронирования по событию и статусу."""
        stmt = (
            select(Reservation)
            .options(selectinload(Reservation.items))
            .where(
                Reservation.event_id == event_id,
                Reservation.status == status,
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
