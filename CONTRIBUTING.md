# Контрибьюция в TD Pay

Этот репозиторий — монорепо: `backend/` (FastAPI) и `frontend/` (Next.js 15).
Разработка ведётся в Docker, на хосте достаточно Docker Desktop / Docker Engine.

## Quickstart

```bash
# 1. Скопировать .env.example в .env и подставить секреты
cp .env.example .env

# 2. Сгенерировать FERNET_KEY (32 байта base64) — пока достаточно заглушки
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# → вставить в .env как FERNET_KEY=...

# 3. Поднять всё
make up

# 4. (Когда появятся миграции в Phase 1) применить их
make migrate
```

Адреса сервисов:

| Сервис | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 (`/docs` — Swagger) |
| MailHog UI | http://localhost:8025 |
| MinIO Console | http://localhost:9001 |
| Postgres | localhost:5432 |
| Redis | localhost:6379 |

## Основные команды

```bash
make help              # список всех команд
make up                # поднять окружение
make down              # остановить
make logs              # логи всех сервисов
make logs svc=backend  # логи одного сервиса

make migrate                      # применить миграции
make migration name=add_users     # новая миграция

make test        # все тесты (backend + frontend)
make lint        # все линты
make typecheck   # mypy + tsc
make format      # ruff format + prettier

make be-shell    # шелл в backend-контейнер
make fe-shell    # шелл в frontend-контейнер
```

## Структура

Подробная архитектура — в [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md).
Модель данных — в [`docs/DATA_MODEL.md`](./docs/DATA_MODEL.md).
API-контракт — в [`docs/API_CONTRACT.md`](./docs/API_CONTRACT.md).
Дорожная карта — [`docs/ROADMAP.md`](./docs/ROADMAP.md).
Правила для ИИ-агентов — [`AGENTS.md`](./AGENTS.md).

## Git

Мы используем **Conventional Commits** (английский, императив, ≤72 символа):

```
feat(api): add magic-link login endpoint
fix(scanner): prevent double check-in race condition
refactor(domain): extract PaymentProvider protocol
test(booking): cover promo code edge cases
chore: bump httpx to 0.28
docs: update REQUIREMENTS with deposit flow
```

Правило: **один коммит = одно логическое изменение**.
Агенты не коммитят без явной команды от пользователя.

## Стиль кода

- **Python:** `ruff format` (88 символов), `ruff check` (E, F, I, B, UP, N, RUF), `mypy --strict`.
- **TypeScript:** Prettier с `singleQuote: true`, ESLint (`next/core-web-vitals`), `strict: true`.
- **Комментарии:** на русском, код/имена — на английском.

## Тесты

- `make test` должен быть зелёным перед PR.
- Для новых доменных сервисов — unit-тесты с покрытием ≥ 85%.
- Race conditions, идемпотентность, tenant-isolation — обязательно покрывать.

## Вопросы

Смотрите [`docs/`](./docs) или спросите в issue.
