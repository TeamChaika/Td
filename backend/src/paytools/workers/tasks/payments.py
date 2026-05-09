"""Arq-задачи для модуля платежей."""

from __future__ import annotations

import logging
from typing import Any

from paytools.core.db import AsyncSessionLocal
from paytools.db.repositories.payment import PaymentRepository
from paytools.db.repositories.reservation import ReservationRepository
from paytools.db.repositories.ticket import TicketRepository
from paytools.domain.payments.service import PaymentService
from paytools.domain.tickets.service import TicketService

logger = logging.getLogger(__name__)


async def expire_pending_payments(ctx: dict[str, Any]) -> int:
    """Cron-задача: истечь просроченные pending платежи.

    Запускается раз в минуту arq-воркером.
    Возвращает количество обработанных платежей.
    """
    async with AsyncSessionLocal() as session:
        async with session.begin():
            reservation_repo = ReservationRepository(session)
            svc = PaymentService(
                session,
                payment_repo=PaymentRepository(session),
                reservation_repo=reservation_repo,
                ticket_service=TicketService(
                    session,
                    ticket_repo=TicketRepository(session),
                    reservation_repo=reservation_repo,
                ),
            )
            count = await svc.expire_pending_payments()

    if count > 0:
        logger.info("Истекли %d платежей", count)

    return count
