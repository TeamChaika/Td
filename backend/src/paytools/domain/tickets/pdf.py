"""PDF-рендеринг билетов через WeasyPrint.

Генерирует PDF-билет из HTML-шаблона с QR-кодом.
"""

from __future__ import annotations

import base64
import io
from uuid import UUID

from weasyprint import HTML


def build_ticket_html(
    *,
    guest_name: str,
    event_title: str,
    event_date: str,
    event_location: str,
    ticket_code: str,
    qr_payload: str,
    guest_index: int,
    total_guests: int,
) -> str:
    """HTML-шаблон одного билета (A4/6 — 100×150mm при печати)."""
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<style>
  @page {{ size: 100mm 150mm; margin: 5mm; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    margin: 0;
    padding: 8mm;
    font-size: 10pt;
    color: #1f2937;
  }}
  .header {{
    text-align: center;
    margin-bottom: 4mm;
  }}
  .event-title {{
    font-size: 14pt;
    font-weight: 700;
    margin: 0;
  }}
  .event-meta {{
    color: #6b7280;
    font-size: 9pt;
    margin-top: 2mm;
  }}
  .guest {{
    text-align: center;
    font-size: 12pt;
    font-weight: 600;
    margin: 6mm 0;
  }}
  .qr-container {{
    text-align: center;
    margin: 6mm 0;
  }}
  .qr-container img {{
    width: 60mm;
    height: 60mm;
  }}
  .code {{
    text-align: center;
    font-family: 'Courier New', monospace;
    font-size: 16pt;
    font-weight: 700;
    letter-spacing: 2px;
    margin: 4mm 0;
    padding: 2mm;
    background: #f3f4f6;
    border-radius: 3mm;
  }}
  .footer {{
    text-align: center;
    color: #9ca3af;
    font-size: 7pt;
    margin-top: 6mm;
  }}
  .divider {{
    border: none;
    border-top: 1px dashed #d1d5db;
    margin: 4mm 0;
  }}
</style>
</head>
<body>
  <div class="header">
    <h1 class="event-title">{event_title}</h1>
    <div class="event-meta">📅 {event_date}</div>
    <div class="event-meta">📍 {event_location}</div>
  </div>

  <hr class="divider">

  <div class="guest">
    {guest_name}
  </div>
  <div style="text-align:center;color:#6b7280;font-size:8pt">
    Гость {guest_index + 1} из {total_guests}
  </div>

  <div class="qr-container">
    <img src="data:image/svg+xml;base64,{_generate_qr_svg(qr_payload)}"
         alt="QR-код билета">
  </div>

  <div class="code">{ticket_code}</div>

  <hr class="divider">

  <div class="footer">
    Билет действителен при предъявлении кода или QR-кода.<br>
    TD Pay — билетная платформа
  </div>
</body>
</html>"""


def _generate_qr_svg(data: str) -> str:
    """Сгенерировать QR-код как SVG (base64)."""
    import qrcode
    import qrcode.image.svg

    factory = qrcode.image.svg.SvgImage
    img = qrcode.make(data, image_factory=factory)
    buf = io.BytesIO()
    img.save(buf)
    return base64.b64encode(buf.getvalue()).decode()


def render_ticket_pdf_bytes(
    *,
    guest_name: str,
    event_title: str,
    event_date: str,
    event_location: str,
    ticket_code: str,
    qr_payload: str,
    guest_index: int = 0,
    total_guests: int = 1,
) -> bytes:
    """Сгенерировать PDF билета как bytes."""
    html_str = build_ticket_html(
        guest_name=guest_name,
        event_title=event_title,
        event_date=event_date,
        event_location=event_location,
        ticket_code=ticket_code,
        qr_payload=qr_payload,
        guest_index=guest_index,
        total_guests=total_guests,
    )
    return HTML(string=html_str).write_pdf()


def render_tickets_pdf_bytes(
    tickets: list[dict],
    *,
    event_title: str,
    event_date: str,
    event_location: str,
) -> bytes:
    """Сгенерировать один PDF со всеми билетами."""
    total = len(tickets)
    pages_html = ""
    for i, t in enumerate(tickets):
        pages_html += build_ticket_html(
            guest_name=f"{t['first_name']} {t['last_name']}",
            event_title=event_title,
            event_date=event_date,
            event_location=event_location,
            ticket_code=t["code"],
            qr_payload=t["qr_payload"],
            guest_index=i,
            total_guests=total,
        )

    combined = f"""<!DOCTYPE html>
<html lang="ru">
<head><meta charset="utf-8"></head>
<body>{pages_html}</body>
</html>"""
    return HTML(string=combined).write_pdf()
