"""Unit-тесты NotificationService и email/SMS шаблонов."""

from __future__ import annotations

import pytest

from paytools.integrations.email import (
    build_magic_link_email_html,
    build_reminder_email_html,
    build_ticket_email_html,
)
from paytools.integrations.sms import build_reminder_sms, build_ticket_sms


class TestTicketEmailTemplate:
    """Тесты HTML-шаблона письма с билетами."""

    def test_contains_ticket_codes(self) -> None:
        html = build_ticket_email_html(
            first_name="Иван",
            event_title="Концерт",
            event_date="2027-01-01T20:00",
            event_location="Москва",
            tickets=[
                {
                    "code": "ABCD-EFGH",
                    "guest_first_name": "Иван",
                    "guest_last_name": "Петров",
                    "guest_index": 0,
                },
                {
                    "code": "JKLM-NPQR",
                    "guest_first_name": "Мария",
                    "guest_last_name": "Иванова",
                    "guest_index": 1,
                },
            ],
            reservation_id="12345678-1234-1234-1234-123456789abc",
        )

        assert "ABCD-EFGH" in html
        assert "JKLM-NPQR" in html
        assert "Иван" in html
        assert "Мария" in html
        assert "Концерт" in html
        assert "Москва" in html
        assert "12345678" in html  # reservation_id[:8]

    def test_contains_html_structure(self) -> None:
        html = build_ticket_email_html(
            first_name="Test",
            event_title="Event",
            event_date="2027-01-01",
            event_location="Location",
            tickets=[
                {
                    "code": "XXXX-YYYY",
                    "guest_first_name": "A",
                    "guest_last_name": "B",
                    "guest_index": 0,
                }
            ],
            reservation_id="00000000-0000-0000-0000-000000000000",
        )

        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "Event" in html


class TestReminderEmailTemplate:
    """Тесты HTML-шаблона письма с напоминанием."""

    def test_contains_event_info(self) -> None:
        html = build_reminder_email_html(
            first_name="Иван",
            event_title="Вечеринка",
            event_date="15.01.2027",
            event_location="Клуб",
            ticket_count=3,
        )

        assert "Иван" in html
        assert "Вечеринка" in html
        assert "Клуб" in html
        assert "3" in html
        assert "состоится сегодня" in html


class TestMagicLinkTemplate:
    """Тесты HTML-шаблона magic-link."""

    def test_contains_link(self) -> None:
        html = build_magic_link_email_html(
            magic_link="https://example.com/magic?token=abc123",
            ttl_minutes=15,
        )

        assert "abc123" in html
        assert "15 минут" in html or "15" in html
        assert "Вход" in html or "войти" in html.lower()


class TestSMSTemplates:
    """Тесты SMS-шаблонов."""

    def test_ticket_sms_contains_code(self) -> None:
        text = build_ticket_sms(
            event_title="Концерт",
            event_date="01.01.2027 20:00",
            ticket_count=2,
            first_code="ABCD-EFGH",
        )

        assert "ABCD-EFGH" in text
        assert "Концерт" in text
        assert "2" in text

    def test_reminder_sms_contains_event(self) -> None:
        text = build_reminder_sms(
            event_title="Фестиваль",
            event_date="01.06.2027",
            event_time="18:00",
        )

        assert "Фестиваль" in text
        assert "18:00" in text
