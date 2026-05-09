"""SMTP-клиент для отправки email через aiosmtplib.

Используется для:
- Отправки билетов после оплаты
- Magic-link для входа
- Напоминаний о событии
"""

from __future__ import annotations

from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import aiosmtplib

from paytools.core.config import get_settings


class EmailError(Exception):
    """Ошибка отправки email."""


async def send_email(
    *,
    to: str,
    subject: str,
    html_body: str,
    text_body: str | None = None,
    attachments: list[tuple[str, bytes, str]] | None = None,
) -> None:
    """Отправить email через SMTP.

    Использует настройки из Settings (smtp_*).
    В dev-окружении письма уходят в MailHog (localhost:1025).

    attachments — список (filename, content_bytes, mime_type).
    """
    settings = get_settings()
    message = MIMEMultipart("mixed")
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Subject"] = subject

    # Тело письма (альтернатива: plain + html)
    body_part = MIMEMultipart("alternative")
    if text_body:
        body_part.attach(MIMEText(text_body, "plain", "utf-8"))
    body_part.attach(MIMEText(html_body, "html", "utf-8"))
    message.attach(body_part)

    # Вложения
    if attachments:
        for filename, content, mime_type in attachments:
            part = MIMEApplication(content, _subtype=mime_type.split("/")[-1])
            part.add_header("Content-Disposition", "attachment", filename=filename)
            message.attach(part)

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user or None,
            password=settings.smtp_password or None,
            use_tls=settings.smtp_tls,
        )
    except Exception as e:
        raise EmailError(f"Failed to send email to {to}: {e}") from e


# ---------------------------------------------------------------------------
# Шаблоны писем (MVP — простые HTML-строки)
# ---------------------------------------------------------------------------


def build_ticket_email_html(
    *,
    first_name: str,
    event_title: str,
    event_date: str,
    event_location: str,
    tickets: list[dict[str, Any]],
    reservation_id: str,
) -> str:
    """HTML-письмо с билетами."""
    ticket_rows = ""
    for t in tickets:
        ticket_rows += f"""
        <tr>
            <td style="padding:12px;border-bottom:1px solid #e5e7eb">
                <strong>{t['code']}</strong>
            </td>
            <td style="padding:12px;border-bottom:1px solid #e5e7eb">
                {t['guest_first_name']} {t['guest_last_name']}
            </td>
            <td style="padding:12px;border-bottom:1px solid #e5e7eb">
                Билет #{t['guest_index'] + 1}
            </td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;max-width:560px;margin:0 auto;padding:24px">
    <h1 style="color:#1f2937;font-size:24px">Ваши билеты</h1>
    <p style="color:#6b7280">Здравствуйте, {first_name}!</p>
    <p style="color:#6b7280">Ваш заказ оплачен. Билеты готовы:</p>

    <div style="background:#f9fafb;border-radius:8px;padding:16px;margin:16px 0">
        <p style="margin:0 0 8px"><strong>{event_title}</strong></p>
        <p style="margin:0 0 8px;color:#6b7280">📅 {event_date}</p>
        <p style="margin:0;color:#6b7280">📍 {event_location}</p>
    </div>

    <table style="width:100%;border-collapse:collapse;margin:16px 0">
        <thead>
            <tr style="background:#f3f4f6">
                <th style="padding:12px;text-align:left">Код</th>
                <th style="padding:12px;text-align:left">Гость</th>
                <th style="padding:12px;text-align:left">Билет</th>
            </tr>
        </thead>
        <tbody>{ticket_rows}</tbody>
    </table>

    <p style="color:#9ca3af;font-size:12px;margin-top:32px">
        Бронь #{reservation_id[:8]}<br>
        Это письмо сгенерировано автоматически.
    </p>
</body>
</html>"""


def build_reminder_email_html(
    *,
    first_name: str,
    event_title: str,
    event_date: str,
    event_location: str,
    ticket_count: int,
) -> str:
    """HTML-письмо с напоминанием о событии."""
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;max-width:560px;margin:0 auto;padding:24px">
    <h1 style="color:#1f2937;font-size:24px">Напоминание о событии</h1>
    <p style="color:#6b7280">Здравствуйте, {first_name}!</p>
    <p style="color:#6b7280">Ваше событие состоится сегодня:</p>

    <div style="background:#f9fafb;border-radius:8px;padding:16px;margin:16px 0">
        <p style="margin:0 0 8px;font-size:18px"><strong>{event_title}</strong></p>
        <p style="margin:0 0 8px;color:#6b7280">📅 {event_date}</p>
        <p style="margin:0;color:#6b7280">📍 {event_location}</p>
    </div>

    <p style="color:#6b7280">У вас {ticket_count} билет(ов). Не забудьте взять их с собой!</p>

    <p style="color:#9ca3af;font-size:12px;margin-top:32px">
        Это письмо сгенерировано автоматически.
    </p>
</body>
</html>"""


def build_magic_link_email_html(
    *,
    magic_link: str,
    ttl_minutes: int = 15,
) -> str:
    """HTML-письмо с magic-link для входа."""
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;max-width:560px;margin:0 auto;padding:24px">
    <h1 style="color:#1f2937;font-size:24px">Вход в TD Pay</h1>
    <p style="color:#6b7280">Нажмите на кнопку чтобы войти:</p>

    <a href="{magic_link}"
       style="display:inline-block;background:#2563eb;color:white;padding:12px 24px;border-radius:6px;text-decoration:none;margin:16px 0">
        Войти
    </a>

    <p style="color:#9ca3af;font-size:12px">
        Ссылка действительна {ttl_minutes} минут.<br>
        Если вы не запрашивали вход — проигнорируйте письмо.
    </p>
</body>
</html>"""
