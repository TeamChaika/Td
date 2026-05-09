"""Сервисный слой билетов.

Отвечает за:
- Выпуск билетов (reservation → tickets)
- Генерация кодов и QR-подписей
- Check-in (сканер)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import string
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from paytools.core.config import get_settings
from paytools.db.models.enums import TicketStatus
from paytools.db.models.ticket import Ticket
from paytools.db.repositories.reservation import ReservationRepository
from paytools.db.repositories.ticket import TicketRepository
from paytools.domain.tickets.errors import (
    TicketAlreadyCheckedInError,
    TicketNotFoundError,
    TicketNotIssuedError,
)

# Алфавит для генерации кодов (без похожих символов: 0/O, 1/I/L)
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 9  # XXXX-XXXX (8 символов + дефис)


def _generate_ticket_code() -> str:
    """Сгенерировать уникальный человекочитаемый код: XXXX-XXXX."""
    chars = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH - 1))
    return f"{chars[:4]}-{chars[4:]}"


def _build_qr_payload(ticket: Ticket) -> str:
    """Собрать подписанный QR-пэйлоад для билета.

    Формат: base64(json({ticket_id, code, event_id, iat})).
    Подпись: HMAC-SHA256 от payload.
    """
    payload_data = {
        "ticket_id": str(ticket.id),
        "code": ticket.code,
        "event_id": str(ticket.event_id),
        "guest_index": ticket.guest_index,
        "first_name": ticket.guest_first_name,
        "last_name": ticket.guest_last_name,
        "iat": int(datetime.now(UTC).timestamp()),
    }
    payload_json = json.dumps(payload_data, separators=(",", ":"))
    payload_b64 = _b64url_encode(payload_json)

    settings = get_settings()
    secret = settings.secret_key.encode()
    sig = hmac.new(secret, payload_b64.encode(), hashlib.sha256).hexdigest()

    return f"{payload_b64}.{sig}"


def _b64url_encode(data: str) -> str:
    """URL-safe base64 без паддинга."""
    import base64

    return base64.urlsafe_b64encode(data.encode()).rstrip(b"=").decode()


def _verify_qr_payload(qr_string: str) -> dict | None:
    """Проверить подпись QR-пэйлоада. Возвращает payload или None."""
    try:
        payload_b64, sig = qr_string.rsplit(".", 1)
    except ValueError:
        return None

    settings = get_settings()
    secret = settings.secret_key.encode()
    expected_sig = hmac.new(secret, payload_b64.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(sig, expected_sig):
        return None

    import base64

    try:
        payload_b64_padded = payload_b64 + "=" * (4 - len(payload_b64) % 4)
        payload_json = base64.urlsafe_b64decode(payload_b64_padded).decode()
        return json.loads(payload_json)  # type: ignore[no-any-return]
    except Exception:
        return None


class TicketService:
    """Доменный сервис билетов."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        ticket_repo: TicketRepository,
        reservation_repo: ReservationRepository,
    ) -> None:
        self.session = session
        self.ticket_repo = ticket_repo
        self.reservation_repo = reservation_repo

    async def issue_for_reservation(
        self,
        org_id: UUID,
        reservation_id: UUID,
    ) -> list[Ticket]:
        """Выпустить билеты для бронирования.

        Создаёт по одному Ticket на каждый ReservationItem × quantity.
        Каждый билет получает уникальный код и QR-пэйлоад.

        Идемпотентен: если билеты уже выпущены — возвращает их.
        """
        existing = await self.ticket_repo.list_for_reservation(reservation_id)
        if existing:
            return existing

        reservation = await self.reservation_repo.get_with_items(reservation_id)
        if reservation is None:
            raise TicketNotIssuedError(
                details={"reservation_id": str(reservation_id)}
            )

        tickets: list[Ticket] = []
        guest_index = 0

        for item in reservation.items or []:
            for _ in range(item.quantity):
                code = await self._generate_unique_code()
                ticket = await self.ticket_repo.create(
                    organization_id=org_id,
                    event_id=reservation.event_id,
                    reservation_id=reservation_id,
                    tariff_id=item.tariff_id,
                    reservation_item_id=item.id,
                    code=code,
                    qr_payload="",  # Заполним после создания (нужен ticket.id)
                    guest_first_name=reservation.first_name,
                    guest_last_name=reservation.last_name,
                    guest_index=guest_index,
                    status=TicketStatus.ISSUED,
                    is_complimentary=(item.price_kopecks == 0),
                )
                # Генерируем QR-пэйлоад с ID билета
                ticket.qr_payload = _build_qr_payload(ticket)
                tickets.append(ticket)
                guest_index += 1

        await self.session.flush()
        return tickets

    async def check_in(
        self,
        ticket_code: str,
        *,
        user_id: UUID | None = None,
    ) -> Ticket:
        """Отметить билет как использованный (чек-ин сканером).

        Принимает человекочитаемый код (XXXX-XXXX) или QR-строку.
        """
        # Пробуем найти по коду
        ticket = await self.ticket_repo.get_by_code(ticket_code)

        # Если не нашли — может быть QR-пэйлоад
        if ticket is None and "." in ticket_code:
            payload = _verify_qr_payload(ticket_code)
            if payload and "ticket_id" in payload:
                ticket = await self.ticket_repo.get(UUID(payload["ticket_id"]))

        if ticket is None:
            raise TicketNotFoundError(details={"code": ticket_code})

        if ticket.status == TicketStatus.CHECKED_IN:
            raise TicketAlreadyCheckedInError(
                details={"ticket_id": str(ticket.id)}
            )

        if ticket.status != TicketStatus.ISSUED:
            raise TicketNotIssuedError(
                details={"ticket_id": str(ticket.id), "status": ticket.status.value}
            )

        now = datetime.now(UTC)
        ticket.status = TicketStatus.CHECKED_IN
        ticket.checked_in_at = now
        ticket.checked_in_by_user_id = user_id

        await self.session.flush()
        return ticket

    async def get_tickets_for_reservation(
        self, reservation_id: UUID
    ) -> list[Ticket]:
        """Получить все билеты бронирования."""
        return await self.ticket_repo.list_for_reservation(reservation_id)

    async def _generate_unique_code(self) -> str:
        """Сгенерировать уникальный код билета (с проверкой на коллизии)."""
        for _ in range(5):
            code = _generate_ticket_code()
            existing = await self.ticket_repo.get_by_code(code)
            if existing is None:
                return code
        # После 5 попыток — добавляем случайный суффикс
        code = _generate_ticket_code()
        suffix = secrets.token_hex(2).upper()[:4]
        return f"{code[:4]}-{suffix}"
