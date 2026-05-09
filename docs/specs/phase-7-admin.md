# Phase 7 — Admin UI (Organizer & Superadmin)

**Цель:** завершить админку организатора (списки, фильтры, экспорты, биллинг) и суперадмина (модерация, общий оборот).

**Параллельные подзадачи:**
- 7a — Backend экспорты, биллинг, audit log (`coder-backend`)
- 7b — Frontend organizer admin полный (`coder-frontend`)
- 7c — Frontend platform admin полный (`coder-frontend`)
- 7d — Tests (`coder-tests`)

**Зависит от:** Phase 6.
**Референсы:** `API_CONTRACT.md § 3, 5`.

---

## 7a. Backend — `coder-backend`

### Экспорты

`domain/exports/service.py`:

- `ExportService.guests_xlsx(event_id) → bytes`
  - Openpyxl
  - Столбцы: №, Код билета, Фамилия, Имя, Email, Телефон, Тариф, Взрослые, Дети, Сумма, Оплачено, Custom fields (динамически), Статус билета, Check-in at
  - Возвращает bytes с `xlsx`

Endpoint: `GET /api/v1/organizer/events/{id}/guests.xlsx`

### Billing

`domain/billing/service.py`:

- `BillingService.charge_commission(payment)` — вызывается из PaymentService после paid:
  - `commission = payment.amount_kopecks * 0.008` (из settings.platform_commission_pct)
  - Создаёт balance_transaction
  - Декрементит organization_balance
- `BillingService.refund_commission(payment, refund_amount)` — возврат пропорционально
- `BillingService.topup(organization_id, amount_kopecks, payment_method) → PaymentIntent`
  - Создаёт отдельный Payment через **платформенный** QRM-ключ
  - После webhook `paid` — increment balance (type=topup)
- `BillingService.adjust(organization_id, amount, note, by_user)` — только superadmin

**Endpoints:**

- `GET /api/v1/organizer/billing/balance` → `{balance_kopecks, last_updated}`
- `GET /api/v1/organizer/billing/transactions?from=&to=&type=`
- `POST /api/v1/organizer/billing/topup` → возвращает QR
- `GET /api/v1/admin/billing/overview` — топ org по обороту, общая комиссия за период
- `POST /api/v1/admin/billing/{org_id}/adjust`

### Audit log

`domain/audit/service.py`:

- Helper `audit_log(session, user, action, resource_type, resource_id, data)`
- Вызывается из всех critical-операций (approve/suspend/refund/qrm_key_update и т.п.)
- Endpoint `GET /api/v1/admin/audit-log?from=&to=&action=` (pagination)

### Модерация событий

- `GET /api/v1/admin/events/pending-moderation`
- `POST /api/v1/admin/events/{id}/approve` → published
- `POST /api/v1/admin/events/{id}/reject` с note → rejected

### Auto-publish toggle

- `POST /api/v1/admin/organizations/{id}/enable-auto-publish` → `auto_publish_enabled=true`

### Dashboard metrics (минимум в MVP)

`domain/dashboard/service.py`:

- `sales_by_day(org_id, from, to)` — агрегация `COUNT(*), SUM(total_kopecks) GROUP BY DATE(paid_at)`
- `summary(org_id)` — total revenue / total tickets / active events

Endpoints:
- `GET /api/v1/organizer/dashboard/sales`
- `GET /api/v1/organizer/dashboard/summary`

### Resend email

- `POST /api/v1/organizer/tickets/{id}/resend-email` — ставит задачу переотправки

### Критерии готовности (7a)

- [ ] XLSX экспорт работает и корректно открывается в Excel
- [ ] Billing charge + refund + topup + adjust работают, баланс консистентен
- [ ] Audit log пишется и читается
- [ ] Модерация событий работает
- [ ] Dashboard данные корректны

---

## 7b. Frontend Organizer — `coder-frontend`

### Страницы

Все под `/admin/*`:

1. **`/admin` (Dashboard)**:
   - Карточки: «Выручка за 7 дней», «Продано билетов», «Активных событий», «Баланс кошелька»
   - График продаж за 30 дней (Recharts)
   - Топ-3 событий по продажам
   - Последние 5 броней

2. **`/admin/events`** (уже есть из Phase 3, улучшить):
   - Действия: Edit / Preview / Duplicate / Archive / View tickets / Export guests

3. **`/admin/tariffs`** — общий список тарифов всех событий (опционально; можно только inline в event)

4. **`/admin/promocodes`** — CRUD промокодов (из Phase 4)

5. **`/admin/reservations`** — таблица:
   - Фильтры: event (select), статус, period
   - Столбцы: дата, событие, гость, сумма, статус
   - Клик → детальная карточка (side-panel или отдельная страница `/admin/reservations/{id}`)

6. **`/admin/tickets`** — таблица билетов:
   - Фильтры: event, статус, period
   - Столбцы: код, гость, событие, тариф, статус
   - Actions: View / Resend email / Refund (if paid)
   - Кнопка «+ Выдать пригласительный»

7. **`/admin/tickets/complimentary/new`** — форма:
   - Event select, tariff select, guest data, quantity, комментарий для истории
   - Submit → создаёт билеты, отправляет email

8. **`/admin/billing`**:
   - Карточка баланса (зелёный если >0, красный если <0 с пояснением «задолженность»)
   - Кнопка «Пополнить» → выбор суммы → показ QR → поллинг
   - График начислений комиссии за 30 дней
   - Таблица транзакций

9. **`/admin/settings`** — уже частично в Phase 2. Добавить:
   - Таб «Уведомления»: toggle «SMS-напоминания гостям», «Email-билеты», «Telegram-уведомления организатору»
   - Таб «Модерация»: статус auto-publish (read-only, включает superadmin)

### Shared компоненты

- `<DataTable>` — обёртка над TanStack Table с пагинацией, фильтрами, sort
- `<DateRangePicker>`
- `<StatusBadge>` — цветные бейджи для статусов
- `<ExportButton>` — кнопка «Экспорт XLSX»
- `<RefundDialog>` — модалка с суммой и причиной

### Критерии готовности (7b)

- [ ] Все 9 разделов работают
- [ ] Responsive (нормально на tablet, usable на mobile)
- [ ] Экспорт XLSX запускается и скачивается
- [ ] Refund работает end-to-end
- [ ] Complimentary билет создаётся, email приходит

---

## 7c. Frontend Platform Admin — `coder-frontend`

### Страницы

Все под `/platform/*`:

1. **`/platform` (Dashboard)**:
   - Карточки: общий оборот платформы, общая комиссия за 30 дней, активные организации
   - График оборота
   - Топ организаций

2. **`/platform/organizations`** — таблица всех организаций:
   - Фильтры: статус
   - Actions: Approve / Suspend / Enable auto-publish / View details
   - `/platform/organizations/{id}` — детали + баланс + последние события + actions

3. **`/platform/moderation`** — очередь событий на модерацию:
   - Таблица pending событий
   - `/platform/moderation/{id}` — превью события + кнопки Approve / Reject with note

4. **`/platform/billing`** — общий биллинг:
   - Список организаций с балансами (задолженности красным)
   - Возможность ручной корректировки баланса (с note)

5. **`/platform/audit`** — audit log viewer с фильтрами

### Критерии готовности (7c)

- [ ] Суперадмин может одобрить регистрацию новой организации
- [ ] Модерация событий работает
- [ ] Биллинг показывает реальные данные
- [ ] Audit log читается

---

## 7d. Tests

### Unit

- `BillingService`: все сценарии charge / refund / adjust / topup (без реального QRM)
- `ExportService.guests_xlsx` — проверяем структуру (columns, rows count)
- `DashboardService`: агрегация корректна

### Integration

- Полный billing flow: paid → charge → balance уменьшился
- Refund → часть комиссии возвращается
- Topup → создаётся отдельный payment, webhook → balance увеличился

### E2E

- Organizer заходит в /admin → видит dashboard → создаёт complimentary → гость получает билет
- Superadmin → одобряет организацию → организация видит в админке «active»

---

## Что вернуть

Скриншоты обеих админок + видео happy-path-а биллинга
