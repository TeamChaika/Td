# TD Pay — Архитектура

> **Продукт:** Tickets & Deposits Pay (TD Pay) — SaaS-платформа для продажи билетов на мероприятия и приёма депозитов, для ресторанов/кафе/клубов и прочих событийных заведений в РФ.
> **Домен:** `tdpay.ru` + wildcard `*.tdpay.ru`.
> **Масштаб MVP:** до ~5 организаторов, ~5 событий/мес, ~1500 билетов/мес.
> **Этот документ — источник истины для всех архитектурных решений.** Кодеры должны следовать ему.

---

## 1. Бизнес-модель

### 1.1. Кто пользуется системой

| Роль | Кто это | Как входит |
|---|---|---|
| **Guest** | Гость, покупающий билет | Без регистрации (guest checkout) |
| **Customer** (v1.1+) | Покупатель с личным кабинетом | Telegram Login (основной) / Email magic-link |
| **Organizer** | Сотрудник организатора (ресторан/клуб) | Email + пароль или Telegram Login |
| **Scanner** | Контролёр на входе (PWA-сканер) | Логин организатора с ограничением роли |
| **Cashier** | Кассир на входе (продажа за наличные, депозиты в iiko) | Логин организатора с ограничением роли |
| **Support** | Поддержка организатора | Логин организатора с ограничением роли |
| **Superadmin** | Мы (владельцы платформы) | Email + пароль (+ опционально Telegram), отдельная админка |

### 1.2. Multi-tenancy

**Схема:** single-tenant UX в MVP, но БД с самого начала готова к multi-tenant.

- Каждая сущность (Event, Tariff, Reservation, Ticket, PromoCode…) имеет `organization_id`.
- Доступ разграничен row-level: organizer видит только свою organization.
- В MVP: wildcard subdomain `*.tdpay.ru` — приложение детектит `subdomain → organization_id`.
- В v1.1: white-label (свой домен организатора через CNAME) + кастомный бренд. Платная опция.
- Корень `tdpay.ru` — **лендинг** (landing page про платформу, форма «Стать организатором»).

### 1.3. Комиссия платформы (1.5%)

**Формула:**
- 0.7% — комиссия QRM (эквайринг), списывается на стороне QRM при зачислении денег организатору.
- 0.8% — комиссия TD Pay, списывается **асинхронно** с внутреннего «кошелька» (баланса) организатора в ЛК.

**Как это работает технически:**

1. Гость оплачивает билет через QRM, используя **QRM-ключ организатора** (деньги идут на его расчётный счёт, минус 0.7% QRM).
2. По webhook от QRM (статус `paid`) система фиксирует факт продажи и **начисляет долг 0.8%** на внутренний биллинг-счёт организатора (`organization_balance`).
3. Организатор **пополняет кошелёк** в ЛК через отдельный QRM-платёж на наш ключ (или перевод по реквизитам).
4. Если баланс < 0 более N дней → автоматическая блокировка создания новых событий (до пополнения).

Это **не требует** статуса платёжного агента, так как мы не держим деньги гостей.

### 1.4. Что в MVP vs v1.x — см. `ROADMAP.md`

---

## 2. Технологический стек

### 2.1. Backend

| Компонент | Выбор | Обоснование |
|---|---|---|
| Язык | Python 3.12 | По AGENTS.md |
| Framework | FastAPI | Async, OpenAPI из коробки |
| ORM | SQLAlchemy 2.x async | По AGENTS.md |
| Миграции | Alembic | По AGENTS.md |
| БД | PostgreSQL 16 | Надёжность, JSON-поля для custom fields |
| Кэш / очередь | Redis 7 | Rate limit, сессии, brokerless для arq |
| Фоновые задачи | **arq** | Простой async-worker на Redis, в 3 раза легче Celery |
| Валидация | Pydantic v2 | По AGENTS.md |
| HTTP-клиент | httpx (async) | Для QRM, SMS Aero, SMTP |
| Линт | ruff | По AGENTS.md |
| Типы | mypy --strict | По AGENTS.md |
| Тесты | pytest + pytest-asyncio | По AGENTS.md |
| Менеджер пакетов | uv | Быстрее poetry |

### 2.2. Frontend

| Компонент | Выбор | Обоснование |
|---|---|---|
| Framework | **Next.js 15 App Router** | SSR для SEO витрин, RSC для скорости |
| Язык | TypeScript strict | По AGENTS.md |
| UI kit | **shadcn/ui** + Tailwind | Дизайн придумываем сами, shadcn — хорошая база |
| Серверное состояние | TanStack Query | По AGENTS.md |
| Формы | React Hook Form + Zod | По AGENTS.md |
| Типы API | openapi-typescript (генерация из OpenAPI) | Автосинхронизация с бэкендом |
| Тесты | Vitest + Testing Library | По AGENTS.md |
| E2E | Playwright | По AGENTS.md |
| Менеджер пакетов | pnpm | По AGENTS.md |

### 2.3. Внешние сервисы

| Сервис | Назначение | Тариф/стоимость |
|---|---|---|
| **QR Manager** (`qrmanager.ru`) | Приём платежей через СБП QR | По договору с организатором |
| **SMS Aero** | SMS-уведомления | ~2₽/SMS |
| **SMTP на VPS (Postfix)** | Email | Бесплатно (DKIM/SPF/DMARC настраиваем сами) |
| **Telegram Bot API** | Уведомления организаторам + логин покупателей | Бесплатно |
| **Timeweb Cloud S3** | Хранение фото событий, PDF-билетов | ~100₽/мес |
| **Timeweb VPS** | Приложение + Postgres + Redis + Postfix | ~5–10 тыс ₽/мес |

### 2.4. Инфраструктура

- **Хостинг:** 1 VPS Timeweb Cloud (рекомендуется 4 CPU / 8 GB / 80 GB SSD для старта).
- **Reverse proxy:** Nginx + certbot (Let's Encrypt, wildcard через DNS-challenge).
- **Оркестрация:** Docker Compose (в MVP; Kubernetes — не нужен).
- **БД:** PostgreSQL в контейнере, volume на диске (с бэкапами).
- **Бэкапы:** ежедневный `pg_dump` → S3 Timeweb (retention 30 дней).
- **CI/CD:** GitHub Actions, автодеплой в main через SSH-скрипт.
- **Мониторинг:** нет в MVP (добавим, когда появятся клиенты).

---

## 3. Структура репозитория

```
PayTools/
├── backend/
│   ├── src/paytools/
│   │   ├── api/v1/
│   │   │   ├── public/          # Эндпоинты для гостей (без auth)
│   │   │   ├── customer/        # Для покупателей (опционально в MVP)
│   │   │   ├── organizer/       # Для организаторов (auth required)
│   │   │   ├── scanner/         # Для PWA-сканера
│   │   │   ├── admin/           # Для superadmin
│   │   │   ├── webhooks/        # Webhook endpoints (QRM, Telegram)
│   │   │   └── schemas/         # Pydantic-схемы
│   │   ├── core/                # config, db, security, tenancy
│   │   ├── domain/              # Бизнес-логика (сервисы, value objects)
│   │   │   ├── events/
│   │   │   ├── bookings/
│   │   │   ├── payments/
│   │   │   ├── tickets/
│   │   │   ├── promocodes/
│   │   │   ├── organizations/
│   │   │   ├── notifications/
│   │   │   └── billing/
│   │   ├── db/                  # SQLAlchemy models, repositories
│   │   ├── integrations/
│   │   │   ├── payments/
│   │   │   │   ├── base.py      # Protocol PaymentProvider
│   │   │   │   └── qrmanager/   # Реализация QRM
│   │   │   ├── sms/
│   │   │   │   └── smsaero.py
│   │   │   ├── telegram/
│   │   │   │   └── bot.py
│   │   │   ├── email/
│   │   │   │   └── smtp.py
│   │   │   └── storage/
│   │   │       └── s3.py
│   │   └── workers/             # arq-задачи
│   ├── alembic/
│   ├── tests/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── (landing)/       # tdpay.ru: лендинг
│   │   │   ├── (tenant)/        # *.tdpay.ru: витрина организатора
│   │   │   │   ├── events/
│   │   │   │   ├── [slug]/
│   │   │   │   ├── pay/[id]/
│   │   │   │   └── ticket/[id]/
│   │   │   ├── admin/           # ЛК организатора (tdpay.ru/admin)
│   │   │   ├── scanner/         # PWA сканер
│   │   │   ├── platform/        # Superadmin
│   │   │   └── api/             # BFF / middleware (детект subdomain)
│   │   ├── components/ui/       # shadcn
│   │   ├── components/brand/    # Компоненты бренда (лого, header)
│   │   ├── features/            # Бизнес-фичи (booking, ticket, scanner)
│   │   ├── lib/
│   │   │   ├── api/             # Клиент к бэкенду + типы из OpenAPI
│   │   │   ├── auth/            # Auth helpers
│   │   │   └── tenant/          # Определение организации по subdomain
│   │   └── types/
│   ├── tests/
│   ├── e2e/
│   └── package.json
├── docs/
│   ├── ARCHITECTURE.md          # этот файл
│   ├── ROADMAP.md
│   ├── DATA_MODEL.md
│   ├── API_CONTRACT.md
│   ├── REQUIREMENTS.md          # заполненный опросник 1
│   ├── REQUIREMENTS-2.md        # заполненный опросник 2
│   ├── RUN_PLAN.md
│   └── specs/
│       ├── phase-0-bootstrap.md
│       ├── phase-1-skeleton.md
│       └── ...
├── docker-compose.yml
├── docker-compose.prod.yml
├── .env.example
└── AGENTS.md
```

---

## 4. Ключевые архитектурные решения

### 4.1. Multi-tenancy на уровне БД

- Во всех бизнес-таблицах — `organization_id UUID NOT NULL REFERENCES organizations(id)`.
- В FastAPI middleware определяется **current organization**:
  - для публичных эндпоинтов — по `subdomain` (`acme.tdpay.ru` → `acme`)
  - для организаторских — по `user.organization_id` из JWT
- Репозитории **обязаны** фильтровать по `organization_id` (не полагаться на Postgres RLS в MVP — это усложняет отладку).
- Unit-тест: проверяем, что каждый репозиторий валится, если `organization_id` не передан.

### 4.2. Payment Provider (абстракция)

```python
# paytools/integrations/payments/base.py

class PaymentProvider(Protocol):
    async def create_payment(
        self,
        *,
        amount_kopecks: int,
        purpose: str,
        notification_url: str,
        customer_email: str | None,
        redirect_url: str | None,
        metadata: dict,
        idempotency_key: str,
    ) -> PaymentIntent: ...

    async def get_status(self, provider_payment_id: str) -> PaymentStatus: ...

    async def refund(
        self,
        provider_payment_id: str,
        amount_kopecks: int,
        reason: str,
    ) -> RefundResult: ...

    def verify_webhook(self, payload: bytes, signature: str) -> bool: ...

    def parse_webhook(self, payload: bytes) -> WebhookEvent: ...
```

В MVP — одна реализация `QrManagerProvider`. Каждый организатор имеет свой `qrm_api_key`, провайдер инстанциируется per-request.

### 4.3. Customization (кастомные поля, capacity-policy и т.д.)

JSON-поля в Postgres (`jsonb`) для гибкости без изменений схемы:

- `events.custom_fields_schema: jsonb` — описание доп. полей формы (имя, тип, required, options)
- `reservations.custom_fields_data: jsonb` — значения, введённые гостем
- `events.schedule: jsonb` — расписание (единичное / серия / период)
- `events.capacity_policy: jsonb` — `{type: 'total' | 'per_tariff' | 'hybrid', ...}`

### 4.4. Статусы (state machines)

**Reservation:**
```
draft → pending_payment → paid
                        ↘ cancelled (expired / user cancel / refund)
```

**Ticket:**
```
issued → checked_in
       ↘ cancelled
       ↘ refunded
```

**Payment:**
```
pending → paid
        ↘ cancelled
        ↘ expired
        ↘ refunded (полностью)
        ↘ partially_refunded (для депозитов в v1.1)
```

**OrganizationBalance transaction:**
```
pending → completed
        ↘ failed
```

Переходы **только через доменные сервисы**, не прямым UPDATE.

### 4.5. Идемпотентность

Все операции создания (reservation, payment, refund) принимают `Idempotency-Key` (клиентский UUID). Ключ → хэш запроса + ссылка на результат в Redis (TTL 24h). Повторный запрос с тем же ключом → возвращаем закэшированный ответ.

### 4.6. Безопасность

- JWT для организаторов (access 15min + refresh 30d в httpOnly cookie).
- Webhook QRM: валидация подписи `P_SIGN` (HMAC).
- Email blocklist (disposable domains) — список в `core/email_blocklist.py`, обновляется по cron.
- CORS: в MVP разрешён только `tdpay.ru` и `*.tdpay.ru`.
- Секреты: `pydantic-settings` + `.env` (никогда не в git).
- Админка (superadmin + organizer) — под basic rate-limit (Redis), даже если общий rate-limit отложен.

### 4.7. Приглашённые (комплиментарные) билеты

**Требование из M.1.** Организатор может создать билет «вручную» без оплаты — для прессы, гостей, спонсоров.

Реализация:
- `POST /api/v1/organizer/tickets/complimentary` — создаёт Reservation со статусом `paid` + Ticket со статусом `issued` + Payment со статусом `complimentary` (новый тип, сумма 0).
- На билете помечается `is_complimentary: true`, тип тарифа `complimentary`.
- Не влияет на биллинг-комиссию 0.8%.
- Отправка билета — обычным флоу (email + PDF).

---

## 5. Доставка билетов (flow after payment)

После webhook `paid` от QRM запускается фоновая задача `arq` с цепочкой:

1. **Генерация Ticket** (один на reservation, один QR).
2. **Рендер PDF** (WeasyPrint, HTML-шаблон в `backend/src/paytools/templates/ticket.html`).
3. **Загрузка PDF в S3** (`tickets/{org_id}/{ticket_id}.pdf`).
4. **Email** (HTML-письмо с inline QR + PDF во вложении).
5. **SMS** через SMS Aero: «Билет оплачен: {short_link}».
6. **Telegram-уведомление** в чат организатора (если подключён бот).
7. **Биллинг:** записать транзакцию на `organization_balance` (долг 0.8%).
8. **Планирование напоминания** за 6 часов до события (`arq.schedule`).

Если шаг N падает — retry с экспоненциальным backoff, но сам билет (п. 1) уже выдан, гость может открыть его по ссылке.

---

## 6. PWA Scanner

- Отдельный роут `/scanner`, доступ по логину организатора с ролью `scanner`/`cashier`/`organizer`.
- Онлайн-only в MVP.
- Утром сканер выбирает событие из сегодняшних → фиксирует `scanner.active_event_id` в локалке.
- QR-пейлоад билета: `{ticket_id}.{signature}` (подпись HMAC на сервере, проверка локально по публичному ключу не делаем — валидация через API).
- `POST /api/v1/scanner/check-in` — проверяет подпись, статус, выставляет `ticket.status = checked_in`.
- Счётчик «вошло/всего» — SSE или polling раз в 5 сек.
- Звук + вибрация: Web Audio API + `navigator.vibrate`.

---

## 7. Telegram-интеграция (один бот на платформу)

- Бот `@TDPayBot` (создадим в BotFather).
- **Привязка организатора к чату:** организатор пишет `/start` в личку → получает токен → в админке нажимает «Привязать Telegram», вводит токен. Потом добавляет бота в групповой чат команды (опционально) и вызывает `/link_chat`.
- **Уведомления:** продажа / возврат / дневной дайджест в 09:00 МСК.
- **Команды:** `/sales_today`, `/events`, `/refund <ticket_id>`.
- **Cashier через бота:** команда `/sell` запускает мини-диалог, кассир выбирает событие → тариф → количество → вводит имя+телефон → получает билет.
- **Login Widget** для покупателей: отдельная фича (Telegram Login Widget на фронте, проверка `hash` на бэке).

---

## 8. Этапность (краткое напоминание, детали в `ROADMAP.md`)

- **MVP (фазы 0–6):** организаторы, события, тарифы, бронь, оплата QRM, билет, email+SMS, PWA-сканер онлайн, биллинг-кошелёк, superadmin
- **v1.0 (фаза 7):** Telegram-бот для организаторов, ЛК покупателя, дашборды, экспорты
- **v1.1:** депозиты, white-label, Early Bird, офлайн-сканер, модерация с auto-publish-правом
- **v1.2:** интеграция iiko, мобильное приложение, рассадка

---

## 9. Неархитектурные решения (по AGENTS.md)

- Git-коммиты — Conventional Commits, не делать без явного запроса.
- Комментарии на русском, код на английском.
- Новые пакеты — по минимуму, с обоснованием.
- Секреты — только через `.env`.
- Переписывать файлы без чтения — нельзя.

---

## 10. Для подагентов

Каждый подагент получает одну **phase-spec** из `docs/specs/phase-NN-*.md` как ТЗ. Этот документ (`ARCHITECTURE.md`) — общий контекст, на который ссылаются все spec'и. Если в spec'е чего-то не хватает — агент читает ARCHITECTURE.md целиком.

Если возникает противоречие между **spec** и **ARCHITECTURE.md** — приоритет у ARCHITECTURE.md, подагент должен сообщить архитектору (т.е. мне) в финальном ответе.
