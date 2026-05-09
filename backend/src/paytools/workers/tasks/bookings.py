"""Arq-задачи для модуля бронирований."""

from __future__ import annotations

import logging
from typing import Any

from paytools.core.db import AsyncSessionLocal
from paytools.db.repositories.email_blocklist import EmailBlocklistRepository
from paytools.db.repositories.event import EventRepository
from paytools.db.repositories.promocode import (
    PromoCodeRepository,
    PromoCodeUsageRepository,
)
from paytools.db.repositories.reservation import ReservationRepository
from paytools.domain.bookings.service import BookingService

logger = logging.getLogger(__name__)


async def expire_draft_reservations(ctx: dict[str, Any]) -> int:
    """Cron-задача: истечь pending_payment брони с expires_at < now.

    Запускается раз в минуту arq-воркером.
    Возвращает количество истёкших бронирований.
    """
    async with AsyncSessionLocal() as session:
        async with session.begin():
            svc = BookingService(
                session,
                reservation_repo=ReservationRepository(session),
                event_repo=EventRepository(session),
                promo_repo=PromoCodeRepository(session),
                usage_repo=PromoCodeUsageRepository(session),
                blocklist_repo=EmailBlocklistRepository(session),
            )
            count = await svc.expire_drafts()

    if count > 0:
        logger.info("Истекли %d бронирований", count)

    return count
