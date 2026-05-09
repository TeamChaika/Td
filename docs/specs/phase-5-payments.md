# Phase 5 — Payments (QRM) & Tickets

**Цель:** гость оплачивает бронь по СБП QR через QR Manager, получает билет с PDF и QR-кодом.

**Параллельные подзадачи:**
- 5a — Backend QRM integration (`coder-backend`)
- 5b — Backend ticket generation (`coder-backend`, после 5a)
- 5c — Frontend pay + ticket pages (`coder-frontend`)
- 5d — Tests (`coder-tests`)

**Зависит от:** Phase 4.
**Референсы:** `ARCHITECTURE.md § 4.2, 5`, `DATA_MODEL.md § 3`, QRM OpenAPI.

---

## 5a. Backend — QRM Integration — `coder-backend`

### Protocol

`integrations/payments/base.py`:

```python
from typing import Protocol

@dataclass
class PaymentIntent:
    provider_payment_id: str
    qr_url: str
    qr_image_url: str
    expires_at: datetime
    raw_response: dict

@dataclass
class PaymentStatusResult:
    status: Literal["pending", "paid", "cancelled", "expired"]
    paid_at: datetime | None
    amount_kopecks: int
    raw: dict

@dataclass
class RefundResult:
    success: bool
    refund_id: str | None
    raw: dict

class PaymentProvider(Protocol):
    async def create_payment(
        self, *,
        amount_kopecks: int,
        purpose: str,
        notification_url: str,
        customer_email: str | None = None,
        redirect_url: str | None = None,
        metadata: dict | None = None,
        ttl_seconds: int = 900,
        idempotency_key: str,
    ) -> PaymentIntent: ...

    async def get_status(self, provider_payment_id: str) -> PaymentStatusResult: ...

    async def refund(
        self, provider_payment_id: str, amount_kopecks: int, reason: str
    ) -> RefundResult: ...

    def verify_webhook_signature(self, payload: bytes, headers: dict[str, str]) -> bool: ...

    def parse_webhook(self, payload: bytes) -> "WebhookEvent": ...
```

### QrManagerProvider

`integrations/payments/qrmanager/provider.py`:

- HTTP-клиент через httpx (async)
- `base_url` из settings, `api_key` / `api_login` — per-organization (инжектятся в constructor)
- Методы:
  - `create_payment()` → `POST /operations/qr-code/` с body согласно `OperationCreate` schema
  - `get_status()` → `GET /api/v2/sse-operations/{id}/qr-status/` (polling; SSE — в v1.0)
  - `refund()` → `POST /operations/refund/`
  - `verify_webhook_signature()` → HMAC проверка `P_SIGN` (см. QRM doc)
  - `parse_webhook()` → парсит `Notification` schema

**Маппинг статусов QRM → наши:**
- `5` → `paid`
- `6` → `cancelled`
- `8` → `expired`
- прочие → `pending`

**Factory:**

```python
async def get_payment_provider(
    organization: Organization,
    session: AsyncSession
) -> PaymentProvider:
    """Инстанциирует провайдера с ключами организации."""
    api_key = decrypt_secret(organization.qrm_api_key_encrypted)
    return QrManagerProvider(
        base_url=settings.qrm_base_url,
        api_key=api_key,
        api_login=organization.qrm_api_login,
    )
```

### Domain — PaymentService

`domain/payments/service.py`:

- `PaymentService.create_for_reservation(reservation_id) → Payment`
  - Идемпотентность через `idempotency_key` (один payment на одну reservation)
  - `purpose = f"Билет: {event.title} / {reservation.id.hex[:8]}"`
  - `notification_url = f"{settings.platform_url}/api/v1/webhooks/payments/qrmanager?org={org_id}"`
  - `customer_email = reservation.email`
  - Создаёт запись в `payments`, статус `pending`
  - Вызывает provider.create_payment(), сохраняет `provider_payment_id`, `qr_url`, `qr_image_url`, `expires_at`

- `PaymentService.handle_webhook(org_id, raw_payload, headers)`
  - Находит organization by id
  - Проверяет signature (organization-specific key)
  - Парсит event
  - Находит Payment по `provider_payment_id`
  - Идемпотентно применяет статус (если уже paid → ничего)
  - Если новый статус `paid`:
    - Payment.status = paid
    - Reservation.status = paid
    - Ставит arq-задачу `issue_tickets(reservation_id)`
    - Начисляет комиссию 0.8%: создаёт `balance_transaction(type=commission_debit)`, обновляет `organization_balance`
  - Если `cancelled/expired`:
    - Payment.status = cancelled/expired
    - Reservation.status = cancelled (возврат capacity)
  - Сохраняет всё в одной транзакции
  - Логирует в `webhook_deliveries`

- `PaymentService.refund(payment_id, amount_kopecks, reason, by_user)`
  - Проверка прав
  - Вызов provider.refund()
  - Обновление payment (`refunded_amount_kopecks += amount`, status = refunded/partially_refunded)
  - Обновление связанных tickets → refunded
  - Возврат комиссии: `balance_transaction(type=refund_credit, amount=amount * 0.008)` — возвращаем нашу долю комиссии пропорционально
  - Уведомление гостю (arq задача)

### API

- `POST /api/v1/public/reservations/{id}/payment` — инициировать QR-платёж
- `GET /api/v1/public/reservations/{id}/status` — для поллинга
- `POST /api/v1/webhooks/payments/qrmanager?org={uuid}` — webhook от QRM
- `POST /api/v1/organizer/payments/{id}/refund`

### Критерии готовности (5a)

- [ ] `PaymentProvider` протокол + `QrManagerProvider` реализация
- [ ] Создание платежа работает с тестовым QRM-ключом
- [ ] Webhook принимает и валидирует подпись
- [ ] Идемпотентность webhook (повторный вызов не ломает)
- [ ] Комиссия 0.8% начисляется в balance
- [ ] Refund работает
- [ ] Все ошибки QRM — обработаны (network, 4xx, 5xx)

---

## 5b. Backend — Ticket Generation — `coder-backend`

### Domain

`domain/tickets/service.py`:

- `TicketService.issue_for_reservation(reservation_id) → list[Ticket]`
  - Для каждого ReservationItem создаётся Ticket(quantity=1) × quantity раз
  - `code` — short unique 8 chars (Crockford base32, без неоднозначных букв)
  - `qr_payload = f"{ticket_id}.{hmac_sign(ticket_id, settings.secret_key)}"`
  - `guest_index` = нумерация внутри reservation
  - Ставит задачи: `render_ticket_pdf(ticket_id)`, `send_ticket_email(reservation_id)`, `send_ticket_sms(reservation_id)`, `notify_organizer_telegram(reservation_id)`

- `TicketService.verify_qr(qr_payload) → Ticket | None`
  - Разбор, проверка HMAC, лукап в БД
  - Возврат None если не прошло (для scanner API)

- `TicketService.check_in(ticket_id, by_user_id) → Ticket`
  - `SELECT ... FOR UPDATE`
  - Проверка статуса (только `issued` → `checked_in`)
  - Сохраняем `checked_in_at`, `checked_in_by_user_id`
  - Пишем audit_log

- `TicketService.issue_complimentary(org_id, event_id, tariff_id, guest_data, by_user)` → Reservation + Ticket со статусами `paid/issued`, Payment со статусом `complimentary` (amount=0). Не начисляет комиссию.

### PDF Rendering

`integrations/pdf/ticket_renderer.py`:

Используем **WeasyPrint** + jinja2-шаблон `backend/src/paytools/templates/ticket.html`.

Шаблон:
- A4 portrait
- Верх: event title + дата/время
- Центр: крупный QR-код (генерация через `qrcode[pil]` → inline base64 SVG)
- Ниже: гость, тариф, количество
- Нижний блок: адрес, правила возврата (`refund_policy`)
- Углы: лого организатора, лого TD Pay (маленький)
- Если билет complimentary — watermark «ПРИГЛАСИТЕЛЬНЫЙ»
- Если есть deposit (v1.1) — дополнительный блок

Рендер → `bytes` → upload в S3 → URL в ticket.pdf_url.

### Arq tasks

`workers/tasks/tickets.py`:
- `issue_tickets(reservation_id)` — главная оркестрирующая задача
- `render_ticket_pdf(ticket_id)` — рендер и upload

### Критерии готовности (5b)

- [ ] Билеты создаются по оплате
- [ ] QR-payload валидный, подписанный
- [ ] PDF генерируется, загружается в S3
- [ ] Complimentary билеты работают
- [ ] `check_in` защищён от гонки

---

## 5c. Frontend — `coder-frontend`

### Страницы

1. **`/pay/{reservation_id}`** (на tenant):
   - Получаем детали через `GET /public/reservations/{id}`
   - Если уже paid → redirect на `/ticket/{ticket_id}?token=...`
   - Показываем QR-код (из `qr_image_url`) + кнопку «Открыть в приложении банка» (`qr_url`)
   - Таймер обратного отсчёта до expires_at
   - Поллинг статуса каждые 3 сек (MVP; SSE — позже)
   - Кнопки: «Отменить и вернуться»

2. **`/ticket/{ticket_id}?token=...`**:
   - Публично доступен по подписанной ссылке
   - Показывает билет: QR (client-side через `qrcode.react`) + все данные
   - Кнопки: «Скачать PDF», «Поделиться», «Показать на весь экран» (для prop-scan)
   - Mobile-first, большой QR, минимум отвлекающего

3. **Админская refund-modal:**
   - В списке payments organizer нажимает «Вернуть»
   - Модалка: сумма (по умолчанию = оставшаяся к возврату), причина (textarea), confirm
   - После успеха — toast + обновление статуса

### Критерии готовности (5c)

- [ ] Страница оплаты с работающим QR
- [ ] Автопереход после оплаты
- [ ] Страница билета, скачивание PDF
- [ ] Refund modal в админке

---

## 5d. Tests — `coder-tests`

### Unit

- `QrManagerProvider`: mock httpx, проверка формирования payload, парсинг ответов, HMAC проверка
- `PaymentService.handle_webhook`: все сценарии (paid, cancelled, повторный вызов, неверная подпись, неизвестный payment)
- `TicketService.issue_for_reservation`: создаёт правильное число билетов
- `TicketService.verify_qr`: валидная/невалидная подпись
- `TicketService.check_in`: double-checkin → конфликт, race test

### Integration

- End-to-end happy path: create reservation → create payment → webhook paid → tickets issued → pdf generated → email sent (проверяем через mailhog)
- Refund: частичный и полный

### Security

- Webhook без правильной подписи → 400, ничего не меняется
- Webhook с чужой org_id → 404

---

## Что вернуть

Скриншоты Swagger + примеры curl + видео happy-path-а.
