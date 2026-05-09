"""Сервисный слой уведомлений.

Отвечает за:
- Отправку билетов (email + SMS) после оплаты
- Отправку напоминаний о событии (email + SMS) за 24ч / 3ч до начала
- Отправку magic-link email
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from paytools.db.models.enums import ReservationStatus, TicketStatus
from paytools.db.models.reservation import Reservation
from paytools.db.repositories.event import EventRepository
from paytools.db.repositories.reservation import ReservationRepository
from paytools.db.repositories.ticket import TicketRepository
from paytools.integrations.email import (
    build_magic_link_email_html,
    build_reminder_email_html,
    build_ticket_email_html,
    send_email,
)
from paytools.integrations.sms import (
    build_reminder_sms,
    build_ticket_sms,
    send_sms,
)

logger = logging.getLogger(__name__)


class NotificationService:
    """Доменный сервис уведомлений."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        reservation_repo: ReservationRepository,
        ticket_repo: TicketRepository,
        event_repo: EventRepository,
    ) -> None:
        self.session = session
        self.reservation_repo = reservation_repo
        self.ticket_repo = ticket_repo
        self.event_repo = event_repo

    # ------------------------------------------------------------------ #
    # Билеты
    # ------------------------------------------------------------------ #

    async def send_ticket_email(
        self, reservation_id: UUID
    ) -> bool:
        """Отправить email с билетами после оплаты.

        Возвращает True если письмо отправлено, False если бронь не найдена.
        """
        reservation = await self.reservation_repo.get_with_items(
            reservation_id
        )
        if reservation is None or reservation.status != ReservationStatus.PAID:
            return False

        tickets = await self.ticket_repo.list_for_reservation(reservation_id)
        if not tickets:
            return False

        event = await self.event_repo.get(reservation.event_id)
        if event is None:
            return False

        schedule = event.schedule or {}
        starts_at = schedule.get("starts_at", "")

        ticket_data = [
            {
                "code": t.code,
                "guest_first_name": t.guest_first_name,
                "guest_last_name": t.guest_last_name,
                "guest_index": t.guest_index,
            }
            for t in tickets
        ]

        html = build_ticket_email_html(
            first_name=reservation.first_name,
            event_title=event.title,
            event_date=starts_at,
            event_location=event.location_name or "",
            tickets=ticket_data,
            reservation_id=str(reservation.id),
        )

        await send_email(
            to=reservation.email,
            subject=f"Билеты: {event.title}",
            html_body=html,
        )
        logger.info(
            "Ticket email sent to %s for reservation %s",
            reservation.email,
            reservation_id,
        )
        return True

    async def send_ticket_sms(
        self, reservation_id: UUID
    ) -> bool:
        """Отправить SMS с кодом билета после оплаты."""
        reservation = await self.reservation_repo.get(reservation_id)
        if reservation is None or reservation.status != ReservationStatus.PAID:
            return False

        tickets = await self.ticket_repo.list_for_reservation(reservation_id)
        if not tickets:
            return False

        event = await self.event_repo.get(reservation.event_id)
        if event is None:
            return False

        schedule = event.schedule or {}
        starts_at = schedule.get("starts_at", "")
        # Форматируем дату для SMS
        try:
            dt = datetime.fromisoformat(starts_at)
            date_str = dt.strftime("%d.%m.%Y %H:%M")
        except (ValueError, TypeError):
            date_str = starts_at

        text = build_ticket_sms(
            event_title=event.title,
            event_date=date_str,
            ticket_count=len(tickets),
            first_code=tickets[0].code,
        )

        phone = reservation.phone
        # Убираем '+' если есть
        if phone.startswith("+"):
            phone = phone[1:]

        await send_sms(phone=phone, text=text)
        logger.info(
            "Ticket SMS sent to %s for reservation %s",
            phone,
            reservation_id,
        )
        return True

    async def send_ticket_notifications(
        self, reservation_id: UUID
    ) -> dict[str, bool]:
        """Отправить и email, и SMS с билетами.

        Возвращает {"email": bool, "sms": bool}.
        """
        email_ok = await self.send_ticket_email(reservation_id)
        sms_ok = await self.send_ticket_sms(reservation_id)
        return {"email": email_ok, "sms": sms_ok}

    # ------------------------------------------------------------------ #
    # Напоминания
    # ------------------------------------------------------------------ #

    async def send_event_reminders(
        self, hours_before: int = 3
    ) -> int:
        """Отправить напоминания о событиях, которые начнутся через N часов.

        Находит все paid-бронирования для событий, начинающихся
        в окне [now + hours_before - 30min, now + hours_before + 30min].
        Отправляет email + SMS с напоминанием.

        Возвращает количество отправленных уведомлений.
        """
        now = datetime.now(UTC)
        window_start = now + timedelta(hours=hours_before) - timedelta(minutes=30)
        window_end = now + timedelta(hours=hours_before) + timedelta(minutes=30)

        # Находим события в нужном окне
        events = await self.event_repo.find_by_time_window(
            window_start.isoformat(), window_end.isoformat()
        )

        sent_count = 0
        for event in events:
            schedule = event.schedule or {}
            starts_at = schedule.get("starts_at", "")

            try:
                dt = datetime.fromisoformat(starts_at)
                date_str = dt.strftime("%d.%m.%Y")
                time_str = dt.strftime("%H:%M")
            except (ValueError, TypeError):
                date_str = starts_at
                time_str = ""

            # Находим paid-бронирования для события
            reservations = await self.reservation_repo.find_by_event_and_status(
                event.id, ReservationStatus.PAID
            )

            for reservation in reservations:
                tickets = await self.ticket_repo.list_for_reservation(
                    reservation.id
                )

                # Email
                try:
                    html = build_reminder_email_html(
                        first_name=reservation.first_name,
                        event_title=event.title,
                        event_date=date_str,
                        event_location=event.location_name or "",
                        ticket_count=len(tickets),
                    )
                    await send_email(
                        to=reservation.email,
                        subject=f"Напоминание: {event.title} сегодня",
                        html_body=html,
                    )
                    sent_count += 1
                except Exception as e:
                    logger.warning(
                        "Failed to send reminder email to %s: %s",
                        reservation.email,
                        e,
                    )

                # SMS
                try:
                    phone = reservation.phone
                    if phone.startswith("+"):
                        phone = phone[1:]

                    sms_text = build_reminder_sms(
                        event_title=event.title,
                        event_date=date_str,
                        event_time=time_str,
                    )
                    await send_sms(phone=phone, text=sms_text)
                    sent_count += 1
                except Exception as e:
                    logger.warning(
                        "Failed to send reminder SMS to %s: %s",
                        reservation.phone,
                        e,
                    )

        return sent_count

    # ------------------------------------------------------------------ #
    # Magic link
    # ------------------------------------------------------------------ #

    async def send_magic_link_email(
        self,
        *,
        email: str,
        token: str,
        ttl_minutes: int = 15,
    ) -> None:
        """Отправить magic-link для входа."""
        from paytools.core.config import get_settings

        settings = get_settings()
        magic_link = (
            f"{settings.platform_url}/admin/magic-link?token={token}"
        )

        html = build_magic_link_email_html(
            magic_link=magic_link,
            ttl_minutes=ttl_minutes,
        )

        await send_email(
            to=email,
            subject="Вход в TD Pay",
            html_body=html,
        )
        logger.info("Magic link email sent to %s", email)
