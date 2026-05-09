"""Integration-тесты email-отправки через реальный SMTP (MailHog).

MailHog запущен в docker-compose на localhost:1025 (SMTP) и :8025 (API).
Проверяет:
- Отправку письма через aiosmtplib
- Что письмо реально доставлено в MailHog
- Корректность HTML-шаблонов в теле письма
"""

from __future__ import annotations

import base64
import re
from email.header import decode_header

import httpx
import pytest

from paytools.integrations.email import (
    build_magic_link_email_html,
    build_reminder_email_html,
    build_ticket_email_html,
    send_email,
)

MAILHOG_API = "http://localhost:8025/api/v2"


def _decode_mime_header(value: str) -> str:
    """Декодировать MIME-заголовок (=?utf-8?b?...?=)."""
    parts = decode_header(value)
    result = ""
    for part, charset in parts:
        if isinstance(part, bytes):
            result += part.decode(charset or "utf-8", errors="replace")
        else:
            result += part
    return result


def _decode_mime_body(raw_body: str) -> str:
    """Декодировать MIME-тело из base64 (MailHog хранит тело как base64)."""
    # Ищем base64 блок после Content-Transfer-Encoding: base64
    match = re.search(
        r"Content-Transfer-Encoding:\s*base64\s*\r?\n\r?\n([A-Za-z0-9+/=\s]+)",
        raw_body,
    )
    if match:
        b64_text = re.sub(r"\s", "", match.group(1))
        try:
            return base64.b64decode(b64_text).decode("utf-8")
        except Exception:
            pass
    # Если не base64 — пробуем найти plain text часть
    text_match = re.search(r"Content-Type: text/plain.*?\r?\n\r?\n(.+)", raw_body, re.DOTALL)
    if text_match:
        return text_match.group(1)
    return raw_body


def _patch_smtp_host_to_localhost(monkeypatch) -> None:
    """В тестах на хосте MailHog доступен как localhost, не mailhog (Docker)."""
    from paytools.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_host", "localhost")
    monkeypatch.setattr(settings, "smtp_port", 1025)
    monkeypatch.setattr(settings, "smtp_user", "")
    monkeypatch.setattr(settings, "smtp_password", "")
    monkeypatch.setattr(settings, "smtp_tls", False)


async def _clear_mailhog() -> None:
    """Удалить все письма из MailHog перед тестом."""
    async with httpx.AsyncClient() as client:
        await client.delete("http://localhost:8025/api/v1/messages")


async def _get_messages() -> list[dict]:
    """Получить все письма из MailHog API."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{MAILHOG_API}/messages")
        resp.raise_for_status()
        data = resp.json()
        return data.get("items", [])


class TestEmailSending:
    """Тесты реальной отправки email через MailHog SMTP."""

    async def test_send_ticket_email(self, monkeypatch) -> None:
        """Отправка письма с билетами → приходит в MailHog."""
        _patch_smtp_host_to_localhost(monkeypatch)
        await _clear_mailhog()

        await send_email(
            to="ivan@example.com",
            subject="Билеты: Концерт",
            html_body=build_ticket_email_html(
                first_name="Иван",
                event_title="Рок-концерт",
                event_date="2027-06-01T20:00",
                event_location="Клуб «Атмосфера»",
                tickets=[
                    {
                        "code": "ABCD-EFGH",
                        "guest_first_name": "Иван",
                        "guest_last_name": "Петров",
                        "guest_index": 0,
                    },
                ],
                reservation_id="12345678-1234-1234-1234-123456789abc",
            ),
        )

        messages = await _get_messages()
        assert len(messages) == 1, f"Expected 1 message, got {len(messages)}"

        msg = messages[0]
        # From может быть test или noreply — зависит от .env
        assert msg["From"]["Mailbox"] in ("test", "noreply")
        to_item = msg["To"][0]
        assert to_item["Mailbox"] == "ivan"
        assert to_item["Domain"] == "example.com"

        headers = msg["Content"]["Headers"]
        raw_subject = headers.get("Subject", [""])[0]
        subject = _decode_mime_header(raw_subject)
        assert "Концерт" in subject or "Билеты" in subject

        body = _decode_mime_body(msg.get("Content", {}).get("Body", ""))
        # Проверяем ключевые элементы HTML
        assert "Рок-концерт" in body
        assert "ABCD-EFGH" in body
        assert "Иван" in body
        assert "12345678" in body  # reservation_id[:8]

    async def test_send_reminder_email(self, monkeypatch) -> None:
        """Отправка напоминания → приходит в MailHog."""
        _patch_smtp_host_to_localhost(monkeypatch)
        await _clear_mailhog()

        await send_email(
            to="maria@example.com",
            subject="Напоминание: Вечеринка сегодня",
            html_body=build_reminder_email_html(
                first_name="Мария",
                event_title="Вечеринка",
                event_date="15.06.2027",
                event_location="Ресторан «Море»",
                ticket_count=2,
            ),
        )

        messages = await _get_messages()
        assert len(messages) == 1

        body = _decode_mime_body(messages[0]["Content"]["Body"])
        assert "Мария" in body
        assert "Вечеринка" in body
        assert "Ресторан" in body
        assert "2" in body

    async def test_send_magic_link_email(self, monkeypatch) -> None:
        """Отправка magic-link → приходит с корректной ссылкой."""
        _patch_smtp_host_to_localhost(monkeypatch)
        await _clear_mailhog()

        await send_email(
            to="admin@example.com",
            subject="Вход в TD Pay",
            html_body=build_magic_link_email_html(
                magic_link="https://tdpay.local/admin/magic-link?token=secret123",
                ttl_minutes=15,
            ),
        )

        messages = await _get_messages()
        assert len(messages) == 1

        body = _decode_mime_body(messages[0]["Content"]["Body"])
        assert "secret123" in body
        assert "tdpay.local" in body

    async def test_send_multiple_emails(self, monkeypatch) -> None:
        """Несколько писем → все доставлены."""
        _patch_smtp_host_to_localhost(monkeypatch)
        await _clear_mailhog()

        for i in range(3):
            await send_email(
                to=f"user{i}@example.com",
                subject=f"Test {i}",
                html_body=f"<p>Email number {i}</p>",
            )

        messages = await _get_messages()
        assert len(messages) == 3

        subjects = {
            msg["Content"]["Headers"].get("Subject", [""])[0]
            for msg in messages
        }
        assert subjects == {"Test 0", "Test 1", "Test 2"}
