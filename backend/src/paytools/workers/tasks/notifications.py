"""Arq-задачи для модуля уведомлений."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from paytools.core.db import AsyncSessionLocal
from paytools.db.repositories.event import EventRepository
from paytools.db.repositories.reservation import ReservationRepository
from paytools.db.repositories.ticket import TicketRepository
from paytools.domain.notifications.service import NotificationService

logger = logging.getLogger(__name__)


async def send_ticket_email(
    ctx: dict[str, Any], reservation_id: str
) -> bool:
    """Отправить email с билетами (вызывается после issue_tickets)."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            reservation_repo = ReservationRepository(session)
            svc = NotificationService(
                session,
                reservation_repo=reservation_repo,
                ticket_repo=TicketRepository(session),
                event_repo=EventRepository(session),
            )
            return await svc.send_ticket_email(UUID(reservation_id))


async def send_ticket_sms(
    ctx: dict[str, Any], reservation_id: str
) -> bool:
    """Отправить SMS с кодом билета (вызывается после issue_tickets)."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            reservation_repo = ReservationRepository(session)
            svc = NotificationService(
                session,
                reservation_repo=reservation_repo,
                ticket_repo=TicketRepository(session),
                event_repo=EventRepository(session),
            )
            return await svc.send_ticket_sms(UUID(reservation_id))


async def send_ticket_notifications(
    ctx: dict[str, Any], reservation_id: str
) -> dict[str, bool]:
    """Отправить email + SMS с билетами."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            reservation_repo = ReservationRepository(session)
            svc = NotificationService(
                session,
                reservation_repo=reservation_repo,
                ticket_repo=TicketRepository(session),
                event_repo=EventRepository(session),
            )
            return await svc.send_ticket_notifications(UUID(reservation_id))


async def schedule_event_reminders_24h(
    ctx: dict[str, Any],
) -> int:
    """Cron-задача: отправить напоминания за 24 часа до события.

    Запускается каждые 30 минут.
    """
    async with AsyncSessionLocal() as session:
        async with session.begin():
            reservation_repo = ReservationRepository(session)
            svc = NotificationService(
                session,
                reservation_repo=reservation_repo,
                ticket_repo=TicketRepository(session),
                event_repo=EventRepository(session),
            )
            count = await svc.send_event_reminders(hours_before=24)

    if count > 0:
        logger.info("Отправлено %d напоминаний за 24ч", count)

    return count


async def schedule_event_reminders_3h(
    ctx: dict[str, Any],
) -> int:
    """Cron-задача: отправить напоминания за 3 часа до события.

    Запускается каждые 15 минут.
    """
    async with AsyncSessionLocal() as session:
        async with session.begin():
            reservation_repo = ReservationRepository(session)
            svc = NotificationService(
                session,
                reservation_repo=reservation_repo,
                ticket_repo=TicketRepository(session),
                event_repo=EventRepository(session),
            )
            count = await svc.send_event_reminders(hours_before=3)

    if count > 0:
        logger.info("Отправлено %d напоминаний за 3ч", count)

    return count
