"""Репозиторий для работы с билетами (Ticket)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select

from paytools.db.models.enums import TicketStatus
from paytools.db.models.ticket import Ticket
from paytools.db.repositories.base import BaseRepository


class TicketRepository(BaseRepository[Ticket]):
    """Репозиторий билетов."""

    model = Ticket

    async def create(self, **data: Any) -> Ticket:
        """Создать билет."""
        ticket = Ticket(**data)
        self.session.add(ticket)
        await self.session.flush()
        return ticket

    async def list_for_reservation(self, reservation_id: UUID) -> list[Ticket]:
        """Все билеты бронирования."""
        stmt = (
            select(Ticket)
            .where(Ticket.reservation_id == reservation_id)
            .order_by(Ticket.guest_index)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_for_reservation(self, reservation_id: UUID) -> int:
        """Количество выпущенных билетов по бронированию."""
        from sqlalchemy import func

        stmt = (
            select(func.count())
            .select_from(Ticket)
            .where(Ticket.reservation_id == reservation_id)
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def get_by_code(self, code: str) -> Ticket | None:
        """Найти билет по человекочитаемому коду (ABCD-1234)."""
        stmt = select(Ticket).where(Ticket.code == code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
