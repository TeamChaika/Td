"""Доменные ошибки для модуля tickets."""

from __future__ import annotations

from paytools.core.errors import ConflictError, NotFoundError


class TicketNotFoundError(NotFoundError):
    """Билет не найден."""

    code = "ticket_not_found"
    default_message = "Билет не найден"


class TicketAlreadyCheckedInError(ConflictError):
    """Билет уже отсканирован."""

    code = "ticket_already_checked_in"
    default_message = "Билет уже использован для входа"


class TicketNotIssuedError(ConflictError):
    """Билет не в статусе issued."""

    code = "ticket_not_issued"
    default_message = "Билет не действителен"
