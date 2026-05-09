"""Unit-тесты PDF-рендеринга билетов (Phase 7)."""

from __future__ import annotations

from paytools.domain.tickets.pdf import (
    build_ticket_html,
    render_ticket_pdf_bytes,
    render_tickets_pdf_bytes,
)


class TestTicketHTML:
    """Тесты HTML-шаблона билета."""

    def test_contains_guest_info(self) -> None:
        html = build_ticket_html(
            guest_name="Иван Петров",
            event_title="Концерт",
            event_date="2027-06-01 20:00",
            event_location="Москва",
            ticket_code="ABCD-EFGH",
            qr_payload="test-payload",
            guest_index=0,
            total_guests=2,
        )

        assert "Иван Петров" in html
        assert "Концерт" in html
        assert "Москва" in html
        assert "ABCD-EFGH" in html
        assert "Гость 1 из 2" in html

    def test_is_valid_html(self) -> None:
        html = build_ticket_html(
            guest_name="Test",
            event_title="Event",
            event_date="2027-01-01",
            event_location="Nowhere",
            ticket_code="XXXX-YYYY",
            qr_payload="data",
            guest_index=5,
            total_guests=10,
        )

        assert "<!DOCTYPE html>" in html
        assert "</html>" in html
        assert "<body>" in html


class TestPDFRendering:
    """Тесты генерации PDF."""

    def test_single_ticket_pdf(self) -> None:
        pdf = render_ticket_pdf_bytes(
            guest_name="Иван Петров",
            event_title="Тестовый концерт",
            event_date="2027-06-01 20:00",
            event_location="Москва, Клуб",
            ticket_code="ABCD-EFGH",
            qr_payload="test-qr-data",
            guest_index=0,
            total_guests=1,
        )

        assert len(pdf) > 1000, f"PDF too small: {len(pdf)} bytes"
        assert pdf[:4] == b"%PDF", f"Not a PDF: {pdf[:10]}"
        assert b"%%EOF" in pdf[-100:], "PDF must end with %%EOF"

    def test_multiple_tickets_pdf(self) -> None:
        tickets = [
            {
                "first_name": "Иван",
                "last_name": "Петров",
                "code": "AAAA-BBBB",
                "qr_payload": "qr1",
            },
            {
                "first_name": "Мария",
                "last_name": "Иванова",
                "code": "CCCC-DDDD",
                "qr_payload": "qr2",
            },
            {
                "first_name": "Пётр",
                "last_name": "Сидоров",
                "code": "EEEE-FFFF",
                "qr_payload": "qr3",
            },
        ]

        pdf = render_tickets_pdf_bytes(
            tickets,
            event_title="Фестиваль",
            event_date="2027-06-01",
            event_location="Парк",
        )

        assert len(pdf) > 3000, f"PDF too small for 3 tickets: {len(pdf)} bytes"
        assert pdf[:4] == b"%PDF"
