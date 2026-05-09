# TD Pay — API Contract

> Все эндпоинты — под `/api/v1`. Формат запросов/ответов — JSON. Ошибки — единый формат `{"error": {"code": "...", "message": "..."}}`.
> Auth через JWT в `Authorization: Bearer <token>` (organizer/scanner/cashier/support/superadmin). Публичные эндпоинты — без auth, определение организации по `X-Tenant-Slug` (из subdomain).
> Idempotency — через заголовок `Idempotency-Key` на POST.

---

## Конвенции

### Ошибки

```json
{
  "error": {
    "code": "validation_error",
    "message": "Поле email не заполнено",
    "details": { "field": "email" },
    "request_id": "uuid"
  }
}
```

Коды:
- `validation_error` (400) — невалидный ввод
- `unauthorized` (401) — нет токена
- `forbidden` (403) — нет прав
- `not_found` (404)
- `conflict` (409) — например, уже есть билет с таким кодом, нет мест
- `rate_limited` (429)
- `payment_error` (502) — ошибка QRM
- `internal_error` (500)

### Пагинация

```
GET /api/v1/...?page=1&per_page=20&sort=-created_at
```

Ответ:
```json
{
  "items": [...],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 157,
    "total_pages": 8
  }
}
```

### Money

Все суммы — `int` в копейках, поля с суффиксом `_kopecks`. На фронте форматируются.

---

## 1. Публичные эндпоинты (для гостя-покупателя)

Требуют заголовок `X-Tenant-Slug: acme` (автоподставляется middleware из subdomain).

### `GET /api/v1/public/events`
Список опубликованных событий организации.

**Query:**
- `page`, `per_page`
- `from`, `to` (фильтр по дате)
- `sort` (default: `schedule.starts_at`)

**Response:**
```json
{
  "items": [
    {
      "id": "uuid",
      "slug": "new-year-2026",
      "title": "Новый год 2026",
      "schedule": {...},
      "location_name": "...",
      "image_card_url": "...",
      "price_from_kopecks": 200000,
      "is_sold_out": false
    }
  ],
  "pagination": {...}
}
```

### `GET /api/v1/public/events/{slug}`
Детали события + тарифы + custom-fields schema.

### `POST /api/v1/public/promocodes/validate`
Проверка промокода (без создания).

**Body:**
```json
{
  "code": "NYE2026",
  "event_id": "uuid",
  "tariff_id": "uuid",
  "email": "guest@example.com",
  "items": [{"tariff_id": "uuid", "quantity": 2}]
}
```

**Response:** валидный промокод + посчитанная скидка, или 422.

### `POST /api/v1/public/reservations`
Создание брони.

Headers: `Idempotency-Key: <uuid>`

**Body:**
```json
{
  "event_id": "uuid",
  "session_id": "uuid|null",
  "first_name": "Иван",
  "last_name": "Иванов",
  "email": "ivan@example.com",
  "phone": "+79991234567",
  "items": [{"tariff_id": "uuid", "quantity": 2}],
  "custom_fields": {"diet": "veg"},
  "promo_code": "NYE2026",
  "referrer_code": null,
  "consent_privacy": true,
  "consent_offer": true
}
```

**Response 201:**
```json
{
  "id": "uuid",
  "status": "pending_payment",
  "total_kopecks": 400000,
  "discount_kopecks": 50000,
  "expires_at": "2026-...",
  "payment_url": "/pay/{reservation_id}"
}
```

### `POST /api/v1/public/reservations/{id}/payment`
Инициирует платёж в QRM, возвращает QR.

**Response:**
```json
{
  "payment_id": "uuid",
  "qr_url": "https://...",
  "qr_image_url": "https://...",
  "amount_kopecks": 400000,
  "expires_at": "..."
}
```

### `GET /api/v1/public/reservations/{id}/status`
Поллинг статуса (в MVP; в v1.1 — SSE).

**Response:**
```json
{
  "status": "paid",
  "tickets": [{"id": "uuid", "code": "ABC123", "pdf_url": "..."}]
}
```

### `GET /api/v1/public/tickets/{id}`
Публичный доступ к билету по секретному токену.

Query: `?token=<signature>`

---

## 2. Webhooks

### `POST /api/v1/webhooks/payments/qrmanager`
Приём уведомлений от QRM о статусе платежа.

Проверка подписи `P_SIGN` (HMAC).

**Body:** см. `CallbackQrCode` / `Notification` в QRM-доке.

**Response:** 200 (всегда, даже если платёж неизвестен — чтобы QRM не ретраил).

Внутри: складываем event в `webhook_deliveries`, ставим задачу `arq` на обработку.

### `POST /api/v1/webhooks/telegram`
Приём апдейтов от Telegram-бота.

---

## 3. Организатор (auth: organizer/support)

Все требуют `Authorization: Bearer <jwt>` и `user.organization_id = resource.organization_id`.

### Auth

- `POST /api/v1/auth/login` — email + password → JWT + refresh
- `POST /api/v1/auth/telegram` — Telegram Login Widget → JWT
- `POST /api/v1/auth/magic-link/request` — отправить magic-link
- `POST /api/v1/auth/magic-link/verify` — подтвердить magic-link → JWT
- `POST /api/v1/auth/refresh` — обновить токен
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me` — текущий пользователь

### Organization

- `GET /api/v1/organizer/organization` — настройки моей организации
- `PATCH /api/v1/organizer/organization` — обновить настройки, бренд, qrm_api_key, smtp
- `POST /api/v1/organizer/organization/qrm/test` — проверить QRM-ключ
- `POST /api/v1/organizer/organization/telegram/link` — привязать Telegram-чат

### Events (CRUD)

- `GET /api/v1/organizer/events` — список с фильтрами
- `POST /api/v1/organizer/events` — создать (draft)
- `GET /api/v1/organizer/events/{id}`
- `PATCH /api/v1/organizer/events/{id}`
- `DELETE /api/v1/organizer/events/{id}` — soft-delete (status=archived)
- `POST /api/v1/organizer/events/{id}/submit` — отправить на модерацию
- `POST /api/v1/organizer/events/{id}/publish` — опубликовать (если auto_publish)
- `POST /api/v1/organizer/events/{id}/image` — upload фото в S3

### Tariffs

- `GET /api/v1/organizer/events/{event_id}/tariffs`
- `POST /api/v1/organizer/events/{event_id}/tariffs`
- `PATCH /api/v1/organizer/tariffs/{id}`
- `DELETE /api/v1/organizer/tariffs/{id}`

### Promo Codes

- `GET /api/v1/organizer/promocodes`
- `POST /api/v1/organizer/promocodes`
- `PATCH /api/v1/organizer/promocodes/{id}`
- `DELETE /api/v1/organizer/promocodes/{id}`
- `GET /api/v1/organizer/promocodes/{id}/usages` — история применений

### Reservations / Tickets

- `GET /api/v1/organizer/reservations` — список с фильтрами (event, status, date)
- `GET /api/v1/organizer/reservations/{id}`
- `GET /api/v1/organizer/tickets` — список билетов
- `GET /api/v1/organizer/tickets/{id}`
- `POST /api/v1/organizer/tickets/complimentary` — создать пригласительный билет
- `POST /api/v1/organizer/tickets/{id}/resend-email` — переотправить билет
- `POST /api/v1/organizer/payments/{id}/refund` — ручной возврат (полный/частичный)

### Экспорты

- `GET /api/v1/organizer/events/{id}/guests.xlsx` — список гостей

### Dashboard (v1.0)

- `GET /api/v1/organizer/dashboard/sales?from=...&to=...` — данные для графика
- `GET /api/v1/organizer/dashboard/summary` — карточки «всего», «за неделю»

### Billing (кошелёк)

- `GET /api/v1/organizer/billing/balance` — текущий баланс
- `GET /api/v1/organizer/billing/transactions` — история
- `POST /api/v1/organizer/billing/topup` — пополнить (создаёт QRM-платёж на наш ключ)

---

## 4. Сканер (auth: scanner/cashier/organizer)

### `GET /api/v1/scanner/events/today`
Сегодняшние события организации.

### `POST /api/v1/scanner/events/{id}/activate`
Зафиксировать, что сканер работает с этим событием.

### `POST /api/v1/scanner/check-in`
**Body:**
```json
{
  "qr_payload": "ticket_id.signature"
  // или
  "code": "ABC123"
}
```

**Response:**
```json
{
  "result": "ok",  // ok | already_used | invalid | wrong_event | cancelled
  "ticket": {
    "id": "...",
    "guest_first_name": "...",
    "guest_last_name": "...",
    "tariff_name": "VIP",
    "guest_index": 1,
    "is_complimentary": false
  },
  "event": {"id": "...", "title": "..."},
  "checked_in_at": "..."
}
```

### `POST /api/v1/scanner/uncheck-in`
Отменить check-in (ошибочный скан).

### `GET /api/v1/scanner/events/{id}/stats`
Счётчик «вошло / всего».

---

## 5. Superadmin

Все — `role=superadmin`.

- `GET /api/v1/admin/organizations` — список всех организаций
- `POST /api/v1/admin/organizations/{id}/approve` — одобрить регистрацию
- `POST /api/v1/admin/organizations/{id}/suspend` — заблокировать
- `POST /api/v1/admin/organizations/{id}/enable-auto-publish` — разрешить автопубликацию
- `POST /api/v1/admin/events/{id}/moderate` — одобрить/отклонить событие
- `GET /api/v1/admin/billing/overview` — общий оборот платформы
- `POST /api/v1/admin/billing/{org_id}/adjust` — ручная корректировка баланса
- `GET /api/v1/admin/audit-log`

---

## 6. Customer (v1.0+)

- `GET /api/v1/customer/tickets` — мои билеты
- `GET /api/v1/customer/tickets/{id}`
- `POST /api/v1/customer/tickets/{id}/refund-request` — запрос на возврат (идёт в support)

---

## 7. Health

- `GET /health` — liveness (просто 200 OK)
- `GET /ready` — readiness (БД, Redis, QRM ping)

---

## 8. Rate limits (MVP — отложено, но архитектурно):

Планируем через Redis + `fastapi-limiter`:
- `POST /public/reservations`: 10/hour/IP
- `POST /auth/login`: 5/min/IP
- `POST /auth/magic-link/request`: 3/hour/email
- `POST /webhooks/*`: unlimited (но проверка подписи)

В MVP отключено флагом `ENABLE_RATE_LIMITS=false`.
