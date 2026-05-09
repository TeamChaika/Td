# TD Pay — Дорожная карта

> Приоритет — **запустить работающую платформу с продажей билетов через QRM максимально быстро**. Потом расширяем.

## Версии

| Версия | Статус | Цель | Что выпускаем |
|---|---|---|---|
| **MVP** | планируется | Первая продажа билета гостю через платформу | Фазы 0–6 |
| **v1.0** | после MVP | Подключение Telegram-бота и первых организаторов | Фазы 7–9 |
| **v1.1** | +1–2 мес | Депозиты, white-label, офлайн-сканер | Фаза 10 |
| **v1.2** | +3–4 мес | Интеграция iiko, мобильное приложение, рассадка | Фаза 11+ |

---

## MVP — детальный состав

**Цель:** гость на `acme.tdpay.ru` видит список событий, покупает билет по СБП-QR, получает email + SMS со ссылкой + PDF, на входе контролёр сканирует QR через PWA.

**Что входит:**

### Backend
- ✅ FastAPI + SQLAlchemy + Alembic + Redis
- ✅ Миграции БД (все таблицы из `DATA_MODEL.md` кроме `deposits*`)
- ✅ Multi-tenancy middleware (определение organization по subdomain / JWT)
- ✅ Auth организатора (email+password) + JWT
- ✅ CRUD событий, тарифов, промокодов
- ✅ Публичные эндпоинты: каталог, детали, бронь, оплата, билет
- ✅ Интеграция QRM: создание QR, webhook, статус
- ✅ Генерация билета + PDF (WeasyPrint)
- ✅ Email (SMTP) с HTML-шаблоном + PDF во вложении
- ✅ SMS через SMS Aero (после оплаты + напоминание за 6 часов)
- ✅ Worker на arq для фоновых задач
- ✅ Биллинг-кошелёк организатора (начисление долга 0.8%)
- ✅ Сканер API (check-in, uncheck-in, stats)
- ✅ Superadmin API (регистрация организаций, модерация событий)
- ✅ Email blocklist (disposable domains)
- ✅ Webhook deliveries log + audit log

### Frontend
- ✅ Лендинг `tdpay.ru` (главная + форма «стать организатором»)
- ✅ Витрина `{slug}.tdpay.ru` (каталог + событие + форма брони)
- ✅ Страницы оплаты и билета
- ✅ Админка `tdpay.ru/admin` для организатора:
  - Dashboard с карточками «продажи за неделю», «баланс»
  - CRUD событий (wizard 3-4 шага)
  - Tariffs inline в event form
  - Promo codes — отдельный раздел
  - Reservations & Tickets — таблица с фильтрами
  - Settings (бренд, QRM-ключ, SMTP, Telegram-чат)
  - Billing (баланс + транзакции + пополнение)
- ✅ Суперадминка `tdpay.ru/platform` (минималка: модерация, список орг.)
- ✅ PWA-сканер `{slug}.tdpay.ru/scanner` (онлайн-only)
- ✅ Публичные страницы: оферта, политика конфиденциальности, контакты

### Infra
- ✅ Docker Compose (dev + prod)
- ✅ Nginx + certbot (wildcard DNS-challenge)
- ✅ Postfix в Docker для email
- ✅ GitHub Actions CI (lint + test + build)
- ✅ Скрипт автодеплоя по SSH на main push
- ✅ Ежедневный бэкап БД в S3

### Не входит в MVP

- ❌ Депозиты → v1.1
- ❌ White-label (свой домен) → v1.1
- ❌ ЛК покупателя → v1.0
- ❌ Telegram-бот (кроме base login widget) → v1.0
- ❌ Офлайн-сканер → v1.1
- ❌ Дашборды с детальной аналитикой → v1.0
- ❌ Рассадка → v1.2
- ❌ iiko интеграция → v1.2
- ❌ Early Bird / временные скидки → v1.1
- ❌ Модерация с правом «auto-publish» → v1.1 (в MVP: все события ручной модерации)
- ❌ Rate limit, капча (feature-flag, выключено) → v1.0
- ❌ Передача билета другому → v1.2
- ❌ Партнёрские коды (поля в БД есть, логика — v1.0)
- ❌ Экспорт XLSX для бухгалтерии (CSV — v1.0) → ✅ в MVP делаем XLSX гостей по событию

---

## Фазы реализации MVP

Каждая фаза = spec-файл в `docs/specs/phase-NN-*.md`. Фазы идут последовательно по зависимостям, но внутри фазы работы параллельны.

### Фаза 0 — Bootstrap (devops)
- Docker Compose (postgres, redis, mailhog, backend, frontend)
- pyproject.toml, package.json, Makefile
- Alembic init
- GitHub Actions шаблоны
- .env.example, CONTRIBUTING.md

### Фаза 1 — Скелет (параллельно BE + FE)

**1a. Backend skeleton** (coder-backend)
- FastAPI app, роутеры pattern
- SQLAlchemy setup, async engine
- Redis client
- Pydantic settings
- Health endpoints
- Error handling middleware
- Logging (structlog)

**1b. Frontend skeleton** (coder-frontend)
- Next.js 15 App Router с группами маршрутов `(landing)` / `(tenant)` / `admin` / `scanner` / `platform`
- Tailwind + shadcn/ui
- TanStack Query provider
- Tenant detection middleware
- OpenAPI-client generation setup
- Base UI components

**1c. DB models & migrations** (coder-backend параллельно с 1a)
- Все модели из `DATA_MODEL.md`
- Первая миграция (baseline)
- Базовые репозитории с auto-tenant-filter

### Фаза 2 — Organizations & Auth

**2a. Backend** (coder-backend)
- Sign-up организатора (публичный endpoint, создаёт Organization + Owner User со статусом pending)
- Login email+password
- JWT + refresh
- Magic-link (отправка + verify)
- Middleware: tenant-context из subdomain или JWT
- Superadmin endpoints: approve organization

**2b. Frontend** (coder-frontend)
- Страница регистрации организатора (на `tdpay.ru/register`)
- Страница логина (`tdpay.ru/admin/login`)
- Magic-link flow
- Middleware: redirect если не авторизован
- Layout админки (sidebar + header с бренд. организации)

**2c. Tests** (coder-tests)
- Unit-тесты AuthService (пароли, JWT)
- Integration-тесты signup/login flow
- Тесты multi-tenant изоляции (организатор A не видит данные B)

### Фаза 3 — Events & Tariffs

**3a. Backend** (coder-backend)
- CRUD events + tariffs
- Upload фото в S3
- Publication flow (draft → pending_moderation → published)
- Публичные endpoints
- Валидация schedule, capacity_policy, custom_fields_schema

**3b. Frontend — админка** (coder-frontend)
- Список событий
- Wizard создания/редактирования (3 шага: основное → тарифы → кастомные поля)
- Preview события
- Отправка на модерацию

**3c. Frontend — витрина** (coder-frontend параллельно)
- Каталог (`{slug}.tdpay.ru/`)
- Страница события (`/events/{slug}`)
- Компонент EventCard
- Применение брендинга организации (logo, color)

**3d. Tests** (coder-tests)
- CRUD events API
- Публикация и модерация

### Фаза 4 — Booking & Promo Codes

**4a. Backend** (coder-backend)
- Создание reservation с расчётом total
- Валидация promo_code (discount calc: percent / fixed_amount / fixed_price)
- Проверка capacity (атомарно, UPDATE ... WHERE sold_count + n <= limit)
- Expiration job для draft-броней (arq)
- Email blocklist check
- CRUD promo_codes в organizer API

**4b. Frontend** (coder-frontend)
- Форма брони с RHF + Zod
- Динамические custom fields
- Live-валидация промокода
- Страница "ожидание оплаты"
- Страница билета (просмотр по токену)
- Админка: CRUD promo codes

**4c. Tests** (coder-tests)
- Unit: BookingService, PromoCodeService (все edge cases)
- Unit: расчёт скидок
- Integration: полный сценарий бронирования без оплаты (до pending_payment)

### Фаза 5 — Payments QRM + Tickets

**5a. Backend** (coder-backend)
- `PaymentProvider` Protocol + `QrManagerProvider`
- Fernet-шифрование qrm_api_key
- Endpoint создания платежа (QR)
- Webhook `/webhooks/payments/qrmanager` с HMAC
- Обработка webhook через arq (идемпотентно)
- Генерация Ticket + HMAC QR payload
- PDF-рендер (WeasyPrint) + upload в S3
- Refund API (ручной из админки)
- Биллинг: начисление 0.8% на organization_balance при paid

**5b. Frontend** (coder-frontend)
- Страница `/pay/{reservation_id}`: показ QR, polling статуса
- После paid: редирект на `/ticket/{id}?token=...`
- Страница билета с крупным QR, share, download PDF
- Админка: refund modal с частичной суммой и причиной

**5c. Tests** (coder-tests)
- Mock QRM provider
- Тесты HMAC подписи webhook
- Тесты state machine payment
- Integration: полный happy-path (бронь → оплата → билет)
- Тесты начисления комиссии

### Фаза 6 — Notifications

**6a. Backend** (coder-backend)
- SMTP клиент (aiosmtplib)
- HTML-шаблон письма билета (jinja2)
- SMS Aero client
- Шаблоны SMS
- arq-задачи: send_ticket_email, send_sms_after_payment, schedule_reminder_sms
- Cron-задача: рассылка напоминаний за 6 часов
- Resend-endpoint в админке

**6b. Tests** (coder-tests)
- Тесты шаблонов (snapshot)
- Тесты расписания напоминаний
- Интеграция через mailhog в dev

### Фаза 7 — Scanner PWA

**7a. Backend** (coder-backend)
- Endpoints scanner/*
- Выбор событий на сегодня
- Check-in с защитой от race (FOR UPDATE)
- Stats endpoint
- Audit каждого check-in

**7b. Frontend** (coder-frontend)
- PWA-манифест
- `/scanner` login → выбор события → сканер
- Использовать `@zxing/browser` или `html5-qrcode`
- Ручной ввод кода
- Звук + вибрация
- Счётчик вошло/всего с polling
- Offline-сообщение (в MVP: «нужен интернет»)

**7c. Tests** (coder-tests)
- E2E Playwright: полный сценарий от покупки до check-in

### Фаза 8 — Platform Admin & Billing

**8a. Backend** (coder-backend)
- Superadmin auth (отдельная таблица/роль уже есть)
- Endpoints admin/*
- Модерация событий (approve/reject)
- Управление организациями (approve/suspend/enable_auto_publish)
- Billing overview + ручная корректировка баланса
- Audit log view

**8b. Frontend** (coder-frontend)
- `/platform` — отдельная админка для superadmin
- Список организаций
- Модерация событий (очередь)
- Биллинг: видеть задолженность всех организаций
- Audit log viewer

**8c. Frontend — billing организатора** (coder-frontend)
- Страница Billing в ЛК организатора
- График начислений комиссии
- Кнопка «пополнить баланс» (создаёт QRM-платёж на наш ключ)
- История транзакций

### Фаза 9 — Deploy & Launch

**9a. DevOps**
- Docker-compose.prod.yml (production-ready)
- Nginx конфиг с wildcard + certbot DNS-challenge
- Postfix + DKIM/SPF/DMARC
- GitHub Actions deploy workflow
- Продакшн .env template + secrets
- Backup script (pg_dump → S3)
- Runbook: как подключить нового организатора, как посмотреть логи

**9b. Reviewer**
- Полный code review MVP
- Security audit (особенно webhook, JWT, RLS)
- Проверка соответствия ARCHITECTURE.md

---

## v1.0 — после MVP

**Приоритет фич:**

1. **Telegram-бот `@TDPayBot`** (1 бот на платформу):
   - Логин покупателей (Login Widget)
   - Уведомления организаторам (через привязку к чату)
   - Команды `/sales_today`, `/events`, `/refund`
   - Дневной дайджест 09:00 МСК
   - Cashier: `/sell` flow

2. **ЛК покупателя** (`tdpay.ru/me` или Telegram WebApp):
   - Список моих билетов (по email/telegram_id)
   - Скачать PDF
   - Запрос на возврат

3. **Дашборды продаж** для организатора:
   - График по дням
   - Топ событий
   - Конверсия по промокодам

4. **Rate limits + блокировка disposable emails**

5. **Партнёрские промокоды** — трекинг кто привёл покупателя, отчёты

6. **Модерация с правом auto-publish** для доверенных организаторов

---

## v1.1 — после v1.0

1. **Депозиты** (по сценарию из REQUIREMENTS-2.md § A):
   - Админ добавляет депозит к существующему билету
   - Гость оплачивает депозит через QRM
   - Admin UI: видит депозиты, помечает «внесено в iiko»
   - Депозит сгорает в день события
   - PDF-билет включает инфо о депозите

2. **White-label**:
   - Custom domain через CNAME
   - Автоматический Let's Encrypt через DNS-challenge
   - Полное скрытие упоминаний TD Pay (платная опция)

3. **Офлайн-сканер** (PWA с IndexedDB):
   - Скачивание списка билетов утром
   - Работа без сети
   - Синхронизация вечером
   - Разрешение конфликтов: first-wins на сервере

4. **Early Bird / временные скидки**:
   - Тариф с `active_until` датой
   - Автоматическое скрытие после срока

5. **Push-уведомления** в PWA

---

## v1.2+ — дальше

- Интеграция iiko (автоматическое внесение депозита на стол)
- Нативное мобильное приложение сканера (iOS/Android)
- Рассадка с выбором мест (SVG-схема зала)
- R-Keeper интеграция
- Расширенная аналитика (воронка, LTV)
- Мультиязычность (ru + en)
- 2FA для админки

---

## Оценка временных затрат (грубо)

| Версия | Недель чистой работы | При параллельной работе команды агентов |
|---|---|---|
| MVP (фазы 0–9) | ~12–16 недель | ~6–8 недель (много параллелизма) |
| v1.0 | ~6–8 недель | ~3–4 недели |
| v1.1 | ~8–10 недель | ~4–5 недель |
| v1.2 | ~12+ недель | ~6+ недель |

> Это грубые оценки. Реальность зависит от сложности багов, скорости обратной связи и настройки окружений (прод-QRM-ключ, SMTP DKIM, домены).
