# TD Pay

[![CI](https://github.com/paytools/tdpay/actions/workflows/ci.yml/badge.svg)](https://github.com/paytools/tdpay/actions/workflows/ci.yml)

**TD Pay** (Tickets & Deposits Pay) — SaaS-платформа для продажи билетов на мероприятия с приёмом оплаты через СБП QR (провайдер: [QR Manager](https://qrmanager.ru)) и последующей обработкой депозитов для ресторанов/кафе/клубов.

> Статус: **Phase 0 — скелет проекта**. Разработка идёт по дорожной карте в [`docs/ROADMAP.md`](./docs/ROADMAP.md).

## Быстрый старт

```bash
cp .env.example .env
make up
# frontend: http://localhost:3000
# backend:  http://localhost:8000/docs
```

Подробнее — в [`CONTRIBUTING.md`](./CONTRIBUTING.md).

## Документация

| Документ | О чём |
|---|---|
| [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) | Архитектура, стек, решения |
| [`docs/DATA_MODEL.md`](./docs/DATA_MODEL.md) | Схема БД |
| [`docs/API_CONTRACT.md`](./docs/API_CONTRACT.md) | REST API |
| [`docs/ROADMAP.md`](./docs/ROADMAP.md) | MVP / v1.0 / v1.1 / v1.2 |
| [`docs/specs/`](./docs/specs) | ТЗ для каждой фазы |
| [`AGENTS.md`](./AGENTS.md) | Правила для ИИ-агентов |

## Стек

- **Backend:** Python 3.12 + FastAPI + SQLAlchemy 2.x async + PostgreSQL 16 + Redis + arq
- **Frontend:** TypeScript strict + Next.js 15 (App Router) + Tailwind + shadcn/ui + TanStack Query
- **Инфра:** Docker Compose (dev), Timeweb Cloud VPS + Nginx + Postfix (prod)

## Лицензия

Proprietary © 2026 TD Pay.
