"""Репозиторий для работы с тарифами (Tariff)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select

from paytools.db.models.enums import ReservationStatus
from paytools.db.models.event import Tariff
from paytools.db.models.reservation import Reservation, ReservationItem
from paytools.db.repositories.base import BaseRepository


class TariffRepository(BaseRepository[Tariff]):
    """Репозиторий тарифов с tenant-фильтрацией."""

    model = Tariff

    async def get_for_org(self, tariff_id: UUID, org_id: UUID) -> Tariff | None:
        """Загрузить тариф, явно фильтруя по org_id.

        Возвращает None, если тариф не существует ИЛИ принадлежит другой org.
        Используется для проверки tenant isolation.
        """
        stmt = select(Tariff).where(
            Tariff.id == tariff_id, Tariff.organization_id == org_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_event(self, event_id: UUID) -> list[Tariff]:
        """Список тарифов события, отсортированный по sort_order."""
        stmt = (
            select(Tariff)
            .where(Tariff.event_id == event_id)
            .order_by(Tariff.sort_order)
        )
        stmt = self._apply_tenant_filter(stmt)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_active_for_event(self, event_id: UUID) -> list[Tariff]:
        """Список активных тарифов события."""
        stmt = (
            select(Tariff)
            .where(
                Tariff.event_id == event_id,
                Tariff.is_active == True,  # noqa: E712
            )
            .order_by(Tariff.sort_order)
        )
        stmt = self._apply_tenant_filter(stmt)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def has_sold_tickets(self, tariff_id: UUID) -> bool:
        """Проверка, есть ли реально проданные билеты по тарифу.

        «Продано» = Reservation.status == 'paid'. Только оплаченные
        резервации считаются. draft/expired/cancelled/pending_payment
        НЕ блокируют изменение тарифа.
        """
        stmt = (
            select(func.count())
            .select_from(ReservationItem)
            .join(Reservation, ReservationItem.reservation_id == Reservation.id)
            .where(
                ReservationItem.tariff_id == tariff_id,
                Reservation.status == ReservationStatus.PAID,
            )
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one()) > 0
