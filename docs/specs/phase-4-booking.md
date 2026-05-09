# Phase 4 — Booking & Promo Codes

**Цель:** гость бронирует билет с указанием количества по тарифам, промокодом и согласием. Драфт хранится 15 минут, потом expire.

**Параллельные подзадачи:**
- 4a — Backend booking + promo (`coder-backend`)
- 4b — Frontend форма брони + промокоды (`coder-frontend`)
- 4c — Tests (`coder-tests`)

**Зависит от:** Phase 3.
**Референсы:** `DATA_MODEL.md § 3, 4`, `API_CONTRACT.md § 1`.

---

## 4a. Backend — `coder-backend`

### Domain

`domain/bookings/service.py`:

- `BookingService.create_reservation(org_id, data) → Reservation`
  - Валидация: event существует, published, тарифы принадлежат event
  - Расчёт subtotal по items
  - Применение promo_code (вызов PromoService.apply)
  - Проверка capacity (см. ниже, атомарно)
  - Email blocklist check
  - Создание Reservation + ReservationItems в транзакции
  - Статус = `pending_payment`
  - `expires_at = now() + 15min`
  - Idempotency: если `idempotency_key` уже был — возвращаем тот же результат

- `BookingService.expire_drafts()` — cron/arq job, раз в минуту ищет `pending_payment AND expires_at < now()` → `cancelled` + возврат capacity.

- `BookingService.cancel(reservation_id, reason)` — переход в cancelled.

`domain/promocodes/service.py`:

- `PromoService.validate(org_id, code, event_id, tariff_id, email, items) → ValidationResult`
  - Находит код (case-insensitive)
  - Проверяет: `is_active`, `active_from/to`, `usage_limit`, `per_user_limit` (по email в promo_code_usages), event/tariff binding
  - Считает discount
- `PromoService.apply(reservation, code)` — валидирует + привязывает к reservation + инкрементирует used_count (атомарно, FOR UPDATE) + пишет в promo_code_usages

**Расчёт скидки:**
- `percent`: `subtotal * discount_value / 10000` (т.к. value хранится ×100)
- `fixed_amount`: `min(discount_value, subtotal)`
- `fixed_price`: действует на конкретный тариф, цена билета становится `discount_value` за штуку

**Capacity check (атомарно):**

```sql
-- Для total policy:
UPDATE events SET sold_count = sold_count + :qty
WHERE id = :event_id AND sold_count + :qty <= (capacity_policy->>'limit')::int
RETURNING sold_count;

-- Для per_tariff:
UPDATE tariffs SET sold_count = sold_count + :qty
WHERE id = :tariff_id AND (capacity_limit IS NULL OR sold_count + :qty <= capacity_limit)
RETURNING sold_count;
```

Если 0 rows updated — кидаем `CapacityError` → 409.

### Компенсирующие операции при expire/cancel

- Декрементируем `sold_count` в events/tariffs
- Декрементируем `used_count` в promo_codes
- Удаляем из `promo_code_usages`

### API

- `POST /api/v1/public/reservations` — см. API_CONTRACT
- `GET /api/v1/public/reservations/{id}` — по id + signed token
- `POST /api/v1/public/promocodes/validate`
- `GET /api/v1/organizer/reservations` — список
- `GET /api/v1/organizer/reservations/{id}`
- `POST /api/v1/organizer/reservations/{id}/cancel`

**Promo codes CRUD (organizer):**

- `GET /api/v1/organizer/promocodes`
- `POST /api/v1/organizer/promocodes` — валидация discount_value в зависимости от type
- `PATCH /api/v1/organizer/promocodes/{id}`
- `DELETE /api/v1/organizer/promocodes/{id}` — запретить если есть usages (soft-delete через is_active)
- `GET /api/v1/organizer/promocodes/{id}/usages`

### Arq tasks

`workers/tasks/bookings.py`:
- `expire_draft_reservations()` — запускается раз в минуту (cron)

### Критерии готовности (4a)

- [ ] Создание брони работает с расчётом скидки
- [ ] Capacity check атомарен (проверить race тестом)
- [ ] Expiration работает
- [ ] Idempotency работает
- [ ] Promo codes CRUD + validate
- [ ] Email blocklist проверяется
- [ ] Tenant isolation

---

## 4b. Frontend — `coder-frontend`

### Страницы

1. **`/events/{slug}/book`** (на tenant-поддомене):
   - Форма RHF + Zod
   - Селект тарифов + количество (`+/-` кнопки)
   - Live-пересчёт итоговой суммы
   - Поля: first_name, last_name, email, phone (с маской), *custom fields из event.custom_fields_schema*
   - Поле «Промокод» с кнопкой «Применить»:
     - debounced auto-validate при 6+ символах
     - Если валиден: показать «Скидка 15% применена: -750 ₽», success toast
     - Если невалиден: inline error
   - Checkboxes:
     - «Я согласен с [офертой](/terms)»
     - «Я согласен на [обработку ПДн](/privacy)»
   - Кнопка «Перейти к оплате» — disabled пока не все validations passed
   - При submit: создаёт reservation, получает `payment_url` → навигация

2. **`/reservations/{id}`** — страница ожидания (пока pending_payment) — просто надпись «Готовим платёж» с редиректом через 1 сек на `/pay/{id}`.

### Компоненты

- `<TariffSelector>` — список тарифов с counter
- `<CustomFieldsForm>` — динамический renderer по schema
- `<PromoCodeInput>` — с debounced validation
- `<PhoneInput>` — маска `+7 (___) ___-__-__`

### UX детали

- Мобильная вёрстка приоритет (основной трафик)
- Sticky bottom bar с итоговой суммой и CTA
- Loading states, optimistic updates для промокода
- Проверка email на disposable *через бэк* (показывать error после submit)

### Критерии готовности (4b)

- [ ] Форма работает end-to-end
- [ ] Все валидации (client + server) отображаются
- [ ] Промокод live-валидируется
- [ ] Custom fields рендерятся по schema
- [ ] Мобильный UX ок

---

## 4c. Tests — `coder-tests`

### Unit

- `PromoService.validate`: все комбинации (expired, usage_limit reached, per_user_limit reached, wrong event/tariff, inactive)
- Расчёт discount для каждого типа
- `BookingService.create`: с промо, без промо, с sold out, с неверным тарифом

### Integration

- Создание брони: happy path
- 409 при sold out
- Idempotency: 2 запроса с одинаковым ключом → один и тот же reservation
- Expiration: создаём бронь, ставим expires_at в прошлое, запускаем job → статус cancelled, sold_count вернулся

### Race condition test

- Спарсенно 50 запросов на последние 10 мест → ровно 10 успешных, 40 с 409

---

## Что вернуть

Стандартный формат (см. Phase 3).
