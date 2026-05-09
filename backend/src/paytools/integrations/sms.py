"""SMS-клиент через SMS Aero HTTP API.

Используется для:
- Отправки билетов после оплаты (код + ссылка)
- Напоминаний о событии

API: https://smsaero.ru/api/
"""

from __future__ import annotations

import base64

import httpx

from paytools.core.config import get_settings


def _basic_auth(email: str, api_key: str) -> str:
    """Собрать Basic Auth заголовок (SMS Aero использует email:api_key)."""
    credentials = base64.b64encode(f"{email}:{api_key}".encode()).decode()
    return f"Basic {credentials}"


class SMSError(Exception):
    """Ошибка отправки SMS."""


async def send_sms(
    *,
    phone: str,
    text: str,
) -> None:
    """Отправить SMS через SMS Aero.

    В dev-окружении (нет smsaero_api_key) — логгирует и не отправляет.
    phone — номер в формате 79001234567.
    """
    settings = get_settings()

    if not settings.smsaero_api_key or not settings.smsaero_email:
        # Dev-окружение: просто логгируем
        import logging

        logger = logging.getLogger(__name__)
        logger.info("SMS (dev): to=%s text=%s", phone, text)
        return

    url = "https://gate.smsaero.ru/v2/sms/send"
    auth = _basic_auth(settings.smsaero_email, settings.smsaero_api_key)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                url,
                json={
                    "number": phone,
                    "text": text,
                    "sign": settings.smsaero_sign,
                },
                headers={
                    "Authorization": auth,
                    "Accept": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()

            if not data.get("success"):
                raise SMSError(
                    f"SMS Aero error: {data.get('message', 'unknown')}"
                )
    except httpx.HTTPError as e:
        raise SMSError(f"Failed to send SMS to {phone}: {e}") from e


def build_ticket_sms(
    *,
    event_title: str,
    event_date: str,
    ticket_count: int,
    first_code: str,
) -> str:
    """Текст SMS с информацией о билетах."""
    return (
        f"TD Pay: {ticket_count} билет(ов) на «{event_title}» "
        f"({event_date}). Код: {first_code}"
    )


def build_reminder_sms(
    *,
    event_title: str,
    event_date: str,
    event_time: str,
) -> str:
    """Текст SMS с напоминанием о событии."""
    return (
        f"TD Pay: Напоминание — сегодня «{event_title}» "
        f"в {event_time}. Не забудьте билеты!"
    )
