# TD Pay — Модель данных (схема БД)

> PostgreSQL 16. Все имена таблиц — `snake_case`, множественное число. Все временные метки — `TIMESTAMPTZ UTC`. Все `id` — `UUID v7` (сортируемые по времени), если не указано иное.
> Денежные суммы — **в копейках** (`BIGINT`), никаких `NUMERIC`.
> Индексы указаны только критичные; полный список — в миграциях.

---

## 1. Организации и пользователи

### `organizations`
Организатор (арендатор). У каждой организации свой поддомен.

| Колонка | Тип | Описание |
|---|---|---|
| `id` | UUID PK | |
| `slug` | VARCHAR(64) UNIQUE NOT NULL | Поддомен: `acme` → `acme.tdpay.ru` |
| `name` | VARCHAR(255) NOT NULL | Название («ООО Чайка») |
| `brand_name` | VARCHAR(255) | Публичное имя («Gastrodvor») |
| `logo_url` | TEXT | Ссылка на S3 |
| `brand_color` | VARCHAR(7) | `#RRGGBB` |
| `contact_email` | VARCHAR(255) | Публичный контакт |
| `contact_phone` | VARCHAR(32) | |
| `legal_entity_type` | ENUM('ip', 'ooo', 'self_employed', 'other') | |
| `legal_inn` | VARCHAR(12) | |
| `legal_name` | VARCHAR(255) | «Индивидуальный предприниматель Иванов И.И.» |
| `legal_address` | TEXT | |
| `qrm_api_key_encrypted` | TEXT | Зашифровано Fernet-ключом из `.env` |
| `qrm_api_login` | VARCHAR(255) | Опционально |
| `qrm_prod_mode` | BOOL DEFAULT false | |
| `custom_domain` | VARCHAR(255) UNIQUE | v1.1 white-label; null → используется `{slug}.tdpay.ru` |
| `white_label_enabled` | BOOL DEFAULT false | v1.1 |
| `smtp_config` | JSONB | Кастомный SMTP организатора (null → шлём от tdpay.ru) |
| `telegram_chat_id` | BIGINT | Для уведомлений о продажах |
| `refund_policy` | TEXT | Текст для билета и оферты |
| `auto_publish_enabled` | BOOL DEFAULT false | Если false — модерация каждого события |
| `status` | ENUM('pending_moderation', 'active', 'suspended') | При регистрации = pending |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | |
| `updated_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | |

**Индексы:** `slug`, `custom_domain`, `status`.

### `users`
Пользователи админки (superadmin, organizer, scanner, cashier, support).

| Колонка | Тип | Описание |
|---|---|---|
| `id` | UUID PK | |
| `organization_id` | UUID FK → organizations(id) | NULL для `superadmin` |
| `email` | VARCHAR(255) UNIQUE NOT NULL | |
| `password_hash` | TEXT | bcrypt (nullable, т.к. Telegram login) |
| `first_name` | VARCHAR(100) | |
| `last_name` | VARCHAR(100) | |
| `phone` | VARCHAR(32) | |
| `role` | ENUM('superadmin', 'organizer', 'scanner', 'cashier', 'support') | |
| `telegram_id` | BIGINT UNIQUE | Для Telegram Login |
| `telegram_username` | VARCHAR(64) | |
| `is_active` | BOOL DEFAULT true | |
| `last_login_at` | TIMESTAMPTZ | |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | |

**Индексы:** `organization_id`, `email`, `telegram_id`.

### `customers` (v1.0+)
Покупатели с ЛК.

| Колонка | Тип | Описание |
|---|---|---|
| `id` | UUID PK | |
| `email` | VARCHAR(255) UNIQUE | Nullable (если вошёл только через Telegram) |
| `phone` | VARCHAR(32) | |
| `first_name` | VARCHAR(100) | |
| `last_name` | VARCHAR(100) | |
| `telegram_id` | BIGINT UNIQUE | |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | |

---

## 2. События и тарифы

### `events`

| Колонка | Тип | Описание |
|---|---|---|
| `id` | UUID PK | |
| `organization_id` | UUID FK NOT NULL | |
| `slug` | VARCHAR(128) NOT NULL | Уникально в рамках организации |
| `title` | VARCHAR(255) NOT NULL | |
| `description_md` | TEXT | Markdown |
| `location_name` | VARCHAR(255) | «Ресторан Чайка» |
| `location_address` | TEXT | Полный адрес |
| `location_coords` | POINT | lat/lng (опционально) |
| `schedule` | JSONB NOT NULL | См. ниже |
| `capacity_policy` | JSONB NOT NULL | См. ниже |
| `sold_count` | INTEGER NOT NULL DEFAULT 0 | Счётчик проданных (для быстрого доступа) |
| `image_card_url` | TEXT | Картинка карточки (S3) |
| `image_background_url` | TEXT | Фон |
| `custom_fields_schema` | JSONB | См. ниже |
| `status` | ENUM('draft', 'pending_moderation', 'published', 'archived', 'rejected') | |
| `moderation_note` | TEXT | Причина отказа от superadmin |
| `published_at` | TIMESTAMPTZ | |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | |
| `updated_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | |

**UNIQUE:** `(organization_id, slug)`.
**Индексы:** `organization_id, status`, `published_at DESC`.

#### `schedule` JSON-схема

```json
// Вариант 1: единичное событие
{
  "type": "single",
  "starts_at": "2026-06-15T18:00:00+03:00",
  "ends_at": "2026-06-15T22:00:00+03:00"
}

// Вариант 2: несколько сеансов
{
  "type": "sessions",
  "sessions": [
    {"id": "uuid", "starts_at": "...", "ends_at": "..."},
    ...
  ]
}

// Вариант 3: период (фестиваль)
{
  "type": "period",
  "starts_at": "2026-07-01T00:00:00+03:00",
  "ends_at": "2026-07-05T23:59:59+03:00"
}
```

#### `capacity_policy` JSON-схема

```json
// Вариант 1: общий лимит
{"type": "total", "limit": 200}

// Вариант 2: лимит на тариф
{"type": "per_tariff"}  // лимиты хранятся в tariffs.capacity_limit

// Вариант 3: гибрид
{"type": "hybrid", "total": 200}  // tariffs.capacity_limit + общий

// Вариант 4: без лимита
{"type": "unlimited"}
```

#### `custom_fields_schema` JSON-схема

```json
[
  {
    "id": "diet",
    "label": "Диетические предпочтения",
    "type": "select",
    "options": ["нет", "вегетарианец", "веган", "без глютена"],
    "required": false
  },
  {
    "id": "comment",
    "label": "Комментарий организатору",
    "type": "text",
    "required": false,
    "max_length": 500
  }
]
```

Типы полей: `text`, `textarea`, `number`, `select`, `multiselect`, `checkbox`, `date`.

### `tariffs`

| Колонка | Тип | Описание |
|---|---|---|
| `id` | UUID PK | |
| `event_id` | UUID FK NOT NULL | |
| `organization_id` | UUID FK NOT NULL | Денормализация для быстрого guard-запроса |
| `name` | VARCHAR(255) NOT NULL | «VIP», «Standard», «Взрослый» |
| `description` | TEXT | |
| `price_kopecks` | BIGINT NOT NULL | |
| `capacity_limit` | INTEGER | NULL = без лимита |
| `sold_count` | INTEGER NOT NULL DEFAULT 0 | |
| `is_complimentary` | BOOL NOT NULL DEFAULT false | Для приглашённых — price=0, создаётся админом |
| `sort_order` | INTEGER DEFAULT 0 | |
| `is_active` | BOOL NOT NULL DEFAULT true | |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | |

**Индексы:** `event_id`.

---

## 3. Бронь, билеты, платежи

### `reservations`
Бронь = намерение купить, до оплаты.

| Колонка | Тип | Описание |
|---|---|---|
| `id` | UUID PK | |
| `organization_id` | UUID FK NOT NULL | |
| `event_id` | UUID FK NOT NULL | |
| `customer_id` | UUID FK → customers(id) | Nullable (guest checkout) |
| `session_id` | UUID | Если у события расписание с сеансами |
| `first_name` | VARCHAR(100) NOT NULL | |
| `last_name` | VARCHAR(100) NOT NULL | |
| `email` | VARCHAR(255) NOT NULL | |
| `phone` | VARCHAR(32) NOT NULL | |
| `custom_fields_data` | JSONB | Значения кастомных полей |
| `items_subtotal_kopecks` | BIGINT NOT NULL | Сумма до скидки |
| `discount_kopecks` | BIGINT NOT NULL DEFAULT 0 | |
| `total_kopecks` | BIGINT NOT NULL | К оплате |
| `promo_code_id` | UUID FK → promo_codes(id) | Nullable |
| `referrer_code` | VARCHAR(64) | Партнёрский код |
| `status` | ENUM('draft', 'pending_payment', 'paid', 'cancelled', 'expired') | |
| `expires_at` | TIMESTAMPTZ | Draft → expired по таймеру (15 мин) |
| `paid_at` | TIMESTAMPTZ | |
| `cancelled_at` | TIMESTAMPTZ | |
| `cancel_reason` | TEXT | |
| `idempotency_key` | VARCHAR(128) UNIQUE | |
| `consent_privacy` | BOOL NOT NULL | Согласие на ПДн |
| `consent_offer` | BOOL NOT NULL | Принятие оферты |
| `user_agent` | TEXT | Для логов |
| `ip` | INET | |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | |

**Индексы:** `organization_id, status`, `event_id, status`, `customer_id`, `status, expires_at`.

### `reservation_items`
Позиции в брони (по одной на каждый тариф × количество).

| Колонка | Тип | Описание |
|---|---|---|
| `id` | UUID PK | |
| `reservation_id` | UUID FK NOT NULL | |
| `tariff_id` | UUID FK NOT NULL | |
| `quantity` | INTEGER NOT NULL CHECK (> 0) | |
| `price_kopecks` | BIGINT NOT NULL | Цена на момент брони (tariff.price может меняться) |
| `subtotal_kopecks` | BIGINT NOT NULL | price × quantity |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | |

### `tickets`
Билет = результат успешной оплаты. Один билет на одну позицию (на одно место/гостя).

| Колонка | Тип | Описание |
|---|---|---|
| `id` | UUID PK | |
| `organization_id` | UUID FK NOT NULL | |
| `event_id` | UUID FK NOT NULL | |
| `reservation_id` | UUID FK NOT NULL | |
| `tariff_id` | UUID FK NOT NULL | |
| `reservation_item_id` | UUID FK NOT NULL | |
| `code` | VARCHAR(16) UNIQUE NOT NULL | Короткий код для ручного ввода сканером |
| `qr_payload` | TEXT NOT NULL | `{ticket_id}.{hmac_signature}` |
| `guest_first_name` | VARCHAR(100) NOT NULL | Дублируется для приглашённых |
| `guest_last_name` | VARCHAR(100) NOT NULL | |
| `guest_index` | SMALLINT NOT NULL | 1, 2, 3… если билетов несколько в одной брони |
| `status` | ENUM('issued', 'checked_in', 'cancelled', 'refunded') | |
| `is_complimentary` | BOOL NOT NULL DEFAULT false | |
| `checked_in_at` | TIMESTAMPTZ | |
| `checked_in_by_user_id` | UUID FK → users(id) | |
| `pdf_url` | TEXT | S3-ссылка |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | |

**Индексы:** `organization_id, event_id, status`, `code`, `reservation_id`.

### `payments`

| Колонка | Тип | Описание |
|---|---|---|
| `id` | UUID PK | |
| `organization_id` | UUID FK NOT NULL | |
| `reservation_id` | UUID FK NOT NULL | |
| `provider` | ENUM('qrmanager', 'complimentary', 'cash') | complimentary = приглашённые, cash = через cashier-роль |
| `provider_payment_id` | VARCHAR(128) | ID операции в QRM |
| `amount_kopecks` | BIGINT NOT NULL | |
| `currency` | VARCHAR(3) NOT NULL DEFAULT 'RUB' | |
| `status` | ENUM('pending', 'paid', 'cancelled', 'expired', 'refunded', 'partially_refunded') | |
| `qr_url` | TEXT | Ссылка на QR-страницу QRM |
| `qr_image_url` | TEXT | PNG с QR |
| `expires_at` | TIMESTAMPTZ | TTL QR-кода |
| `paid_at` | TIMESTAMPTZ | |
| `refunded_at` | TIMESTAMPTZ | |
| `refunded_amount_kopecks` | BIGINT NOT NULL DEFAULT 0 | |
| `provider_payload` | JSONB | Сырой ответ QRM |
| `webhook_events` | JSONB[] | История событий от QRM |
| `idempotency_key` | VARCHAR(128) UNIQUE | |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | |

**Индексы:** `provider_payment_id`, `reservation_id`, `status`.

---

## 4. Промокоды

### `promo_codes`

| Колонка | Тип | Описание |
|---|---|---|
| `id` | UUID PK | |
| `organization_id` | UUID FK NOT NULL | |
| `code` | VARCHAR(64) NOT NULL | Хранится `upper()` |
| `description` | TEXT | |
| `discount_type` | ENUM('percent', 'fixed_amount', 'fixed_price') | |
| `discount_value` | BIGINT NOT NULL | Для percent — ×100 (1500 = 15%), для fixed_amount/price — копейки |
| `event_id` | UUID FK → events(id) | Null = на любое событие организации |
| `tariff_id` | UUID FK → tariffs(id) | Null = на любой тариф |
| `usage_limit` | INTEGER | Null = без лимита |
| `used_count` | INTEGER NOT NULL DEFAULT 0 | |
| `per_user_limit` | INTEGER | Обычно 1 |
| `active_from` | TIMESTAMPTZ | |
| `active_to` | TIMESTAMPTZ | |
| `is_active` | BOOL NOT NULL DEFAULT true | |
| `is_affiliate` | BOOL NOT NULL DEFAULT false | Партнёрский (трекинг кто привёл) |
| `affiliate_user_id` | UUID FK → users(id) | Владелец партнёрского кода |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | |

**UNIQUE:** `(organization_id, code)`.
**Индексы:** `organization_id, is_active`.

### `promo_code_usages`
Лог применений — чтобы enforce'ить `per_user_limit`.

| Колонка | Тип | Описание |
|---|---|---|
| `id` | UUID PK | |
| `promo_code_id` | UUID FK NOT NULL | |
| `reservation_id` | UUID FK NOT NULL | |
| `email` | VARCHAR(255) NOT NULL | Для per-user check |
| `discount_kopecks` | BIGINT NOT NULL | |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | |

**Индексы:** `promo_code_id, email`.

---

## 5. Биллинг платформы (комиссия 0.8%)

### `organization_balance`
Один счёт на организацию.

| Колонка | Тип | Описание |
|---|---|---|
| `organization_id` | UUID PK FK → organizations(id) | |
| `balance_kopecks` | BIGINT NOT NULL DEFAULT 0 | Может быть отрицательным (задолженность) |
| `updated_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | |

### `balance_transactions`

| Колонка | Тип | Описание |
|---|---|---|
| `id` | UUID PK | |
| `organization_id` | UUID FK NOT NULL | |
| `type` | ENUM('commission_debit', 'topup', 'manual_adjustment', 'refund_credit') | |
| `amount_kopecks` | BIGINT NOT NULL | Может быть отрицательным |
| `balance_after_kopecks` | BIGINT NOT NULL | Для audit trail |
| `related_payment_id` | UUID FK → payments(id) | |
| `description` | TEXT | |
| `created_by_user_id` | UUID FK → users(id) | Для manual_adjustment |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | |

**Индексы:** `organization_id, created_at DESC`.

---

## 6. Депозиты (v1.1, pre-created schema)

### `deposits`

| Колонка | Тип | Описание |
|---|---|---|
| `id` | UUID PK | |
| `organization_id` | UUID FK NOT NULL | |
| `ticket_id` | UUID FK NOT NULL | Депозит привязан к билету |
| `reservation_id` | UUID FK NOT NULL | |
| `table_number` | VARCHAR(32) | Какой стол |
| `initial_amount_kopecks` | BIGINT NOT NULL | |
| `remaining_amount_kopecks` | BIGINT NOT NULL | Уменьшается при списании |
| `payment_id` | UUID FK → payments(id) | Отдельный платёж за депозит |
| `status` | ENUM('pending_payment', 'active', 'partially_used', 'fully_used', 'expired', 'refunded') | |
| `expires_at` | TIMESTAMPTZ NOT NULL | Конец дня события |
| `synced_to_iiko` | BOOL NOT NULL DEFAULT false | Внёс ли админ в iiko |
| `iiko_order_id` | VARCHAR(128) | ID заказа в iiko (v1.2) |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | |

### `deposit_transactions`

| Колонка | Тип | Описание |
|---|---|---|
| `id` | UUID PK | |
| `deposit_id` | UUID FK NOT NULL | |
| `amount_kopecks` | BIGINT NOT NULL | |
| `type` | ENUM('charge', 'refund', 'adjustment') | |
| `note` | TEXT | |
| `created_by_user_id` | UUID FK → users(id) | |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | |

---

## 7. Системные

### `idempotency_keys`
Только если не хватит Redis.

### `webhook_deliveries`

| Колонка | Тип | Описание |
|---|---|---|
| `id` | UUID PK | |
| `provider` | VARCHAR(64) | qrmanager |
| `event_type` | VARCHAR(64) | |
| `payload` | JSONB NOT NULL | |
| `headers` | JSONB | |
| `signature_valid` | BOOL | |
| `processed` | BOOL DEFAULT false | |
| `processing_error` | TEXT | |
| `related_payment_id` | UUID | |
| `received_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | |

### `audit_log`
Для critical-actions (создание организации, refund, изменение qrm_api_key и т.п.).

| Колонка | Тип | Описание |
|---|---|---|
| `id` | UUID PK | |
| `organization_id` | UUID | |
| `user_id` | UUID | |
| `action` | VARCHAR(128) | `organization.create`, `payment.refund`, etc. |
| `resource_type` | VARCHAR(64) | |
| `resource_id` | UUID | |
| `data` | JSONB | Before/after |
| `ip` | INET | |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | |

### `email_blocklist`

| Колонка | Тип | Описание |
|---|---|---|
| `domain` | VARCHAR(255) PK | `mail.tm`, `10minutemail.com`, ... |
| `added_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | |
| `source` | VARCHAR(64) | `manual` / `disposable_list_v1` |

---

## 8. Правила, обязательные для кодеров

1. **Все денежные поля — `BIGINT` в копейках.** Никаких `NUMERIC`, `DECIMAL`, `FLOAT`.
2. **Все timestamps — `TIMESTAMPTZ`**, хранение в UTC, отображение — Europe/Moscow.
3. **Все FK — `ON DELETE RESTRICT`** (удаление только через soft-delete или явный cascade в коде).
4. **В каждой бизнес-таблице обязательно `organization_id`** (кроме `customers`, `users.superadmin`, системных).
5. **Не использовать SERIAL/BIGSERIAL**, только `UUID v7` (генерация в Python через `uuid_utils.uuid7()`).
6. **`created_at` / `updated_at`** везде, `updated_at` обновляется триггером или в SQLAlchemy `onupdate`.
7. **Деньги: комментарий `-- kopecks`** в миграции обязательно, чтобы никто не забыл.
8. **Индексы на `status`-колонках** только если часто фильтруем по ним.
9. **Партиционирование `audit_log` и `webhook_deliveries`** по месяцу — в v1.1, не в MVP.
10. **Миграции Alembic** — только автогенерация + ручной review. Не писать SQL руками без генерации.
