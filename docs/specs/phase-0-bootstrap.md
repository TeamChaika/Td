# Phase 0 — Bootstrap

**Исполнитель:** `devops`
**Зависимости:** нет
**Продолжительность:** 1 шаг
**Цель:** подготовить всю инфраструктуру для параллельной работы остальных фаз.

---

## Что нужно сделать

### 1. Docker Compose (dev)

Файл `docker-compose.yml` в корне репозитория:

- `postgres:16-alpine` — порт 5432, volume, env POSTGRES_USER/PASSWORD/DB
- `redis:7-alpine` — порт 6379
- `mailhog/mailhog` — порты 1025 (SMTP) и 8025 (UI)
- `minio/minio` — для локальной S3-эмуляции (порт 9000 + console 9001)
- `backend` — build из `./backend`, volume на src для hot reload (uvicorn --reload)
- `frontend` — build из `./frontend`, volume на src (Next.js dev)
- `worker` — тот же образ что backend, запускает `arq paytools.workers.main.WorkerSettings`

Все сервисы в одной сети `tdpay_net`. Healthchecks для postgres/redis.

### 2. Backend pyproject.toml

`backend/pyproject.toml`:

```toml
[project]
name = "paytools"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "sqlalchemy[asyncio]>=2.0.36",
    "asyncpg>=0.30",
    "alembic>=1.14",
    "pydantic>=2.10",
    "pydantic-settings>=2.7",
    "redis>=5.2",
    "arq>=0.26",
    "httpx>=0.28",
    "aiosmtplib>=3.0",
    "jinja2>=3.1",
    "weasyprint>=63",
    "uuid-utils>=0.10",
    "bcrypt>=4.2",
    "pyjwt[crypto]>=2.10",
    "cryptography>=44",
    "structlog>=24.4",
    "python-multipart>=0.0.18",
    "boto3>=1.35",
    "openpyxl>=3.1",
    "qrcode[pil]>=8.0",
    "email-validator>=2.2",
]

[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.25",
    "pytest-cov>=6.0",
    "httpx>=0.28",
    "ruff>=0.8",
    "mypy>=1.13",
    "types-redis",
]

[tool.ruff]
line-length = 88
target-version = "py312"
[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "N", "RUF"]

[tool.mypy]
strict = true
python_version = "3.12"
plugins = ["pydantic.mypy"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

Используй **uv** как менеджер пакетов: `uv pip install -e ".[dev]"`.

Создать минимальный `backend/src/paytools/__init__.py` и `backend/src/paytools/main.py` с заглушкой FastAPI-приложения (`@app.get("/health")`), чтобы контейнер запускался.

### 3. Frontend package.json

`frontend/package.json`:

```json
{
  "name": "tdpay-frontend",
  "private": true,
  "packageManager": "pnpm@9",
  "scripts": {
    "dev": "next dev --port 3000",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "type-check": "tsc --noEmit",
    "test": "vitest",
    "e2e": "playwright test",
    "openapi:gen": "openapi-typescript http://localhost:8000/openapi.json -o src/types/api.d.ts"
  },
  "dependencies": {
    "next": "^15",
    "react": "^19",
    "react-dom": "^19",
    "@tanstack/react-query": "^5",
    "react-hook-form": "^7",
    "@hookform/resolvers": "^3",
    "zod": "^3",
    "ofetch": "^1",
    "clsx": "^2",
    "tailwind-merge": "^2",
    "class-variance-authority": "^0.7",
    "lucide-react": "^0.400",
    "qrcode.react": "^4",
    "html5-qrcode": "^2",
    "date-fns": "^4"
  },
  "devDependencies": {
    "@types/node": "^22",
    "@types/react": "^19",
    "@types/react-dom": "^19",
    "typescript": "^5.7",
    "tailwindcss": "^3.4",
    "postcss": "^8",
    "autoprefixer": "^10",
    "eslint": "^9",
    "eslint-config-next": "^15",
    "prettier": "^3",
    "vitest": "^2",
    "@testing-library/react": "^16",
    "@testing-library/jest-dom": "^6",
    "msw": "^2",
    "@playwright/test": "^1",
    "openapi-typescript": "^7",
    "@types/qrcode": "^1"
  }
}
```

Установи через `pnpm install`. Инициализируй shadcn через `pnpm dlx shadcn@latest init` (тёма dark, Tailwind CSS variables). Добавь базовые компоненты: `button`, `input`, `form`, `label`, `card`, `dialog`, `toast`, `table`, `dropdown-menu`.

Минимальный `frontend/src/app/layout.tsx` и `frontend/src/app/page.tsx` (заглушка).

### 4. Alembic

```
backend/alembic.ini
backend/alembic/env.py
backend/alembic/versions/
```

В `env.py` — async engine, читает DATABASE_URL из env, пока пустая metadata (модели появятся в Phase 1). **Не создавать baseline-миграцию** — это сделают в Phase 1.

### 5. .env.example

В корне репозитория, покрывающий все сервисы:

```bash
# Backend
DATABASE_URL=postgresql+asyncpg://tdpay:tdpay@postgres:5432/tdpay
REDIS_URL=redis://redis:6379/0
SECRET_KEY=change-me-min-32-chars
FERNET_KEY=           # base64, 32 bytes, генерировать через Python
JWT_SECRET=change-me
JWT_ACCESS_TTL_MIN=15
JWT_REFRESH_TTL_DAYS=30

# S3
S3_ENDPOINT=http://minio:9000
S3_BUCKET=tdpay
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_REGION=ru-1

# SMTP (dev: mailhog)
SMTP_HOST=mailhog
SMTP_PORT=1025
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=noreply@tdpay.local
SMTP_TLS=false

# SMS Aero (пусто в dev)
SMSAERO_EMAIL=
SMSAERO_API_KEY=
SMSAERO_SIGN=TDPay

# QRM
QRM_BASE_URL=https://app.devwapiserv.qrm.ooo

# Telegram (пусто в dev)
TELEGRAM_BOT_TOKEN=

# Platform
PLATFORM_DOMAIN=tdpay.local
PLATFORM_COMMISSION_PCT=0.8

# Feature flags
ENABLE_RATE_LIMITS=false
ENABLE_CAPTCHA=false

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_PLATFORM_DOMAIN=tdpay.local
```

### 6. Makefile (или Taskfile)

Команды:
- `make up` — docker compose up -d
- `make down` — docker compose down
- `make migrate` — запустить alembic upgrade head
- `make migration name=add_xxx` — alembic revision --autogenerate
- `make be-shell` / `make fe-shell` — войти в контейнер
- `make be-test` / `make fe-test`
- `make be-lint` / `make fe-lint`
- `make logs` — tail логов

### 7. GitHub Actions

Два workflow:

**`.github/workflows/ci.yml`** — на PR:
- backend: ruff + mypy + pytest
- frontend: eslint + tsc + vitest
- сборка Docker-образов (только проверка что билдится)

**`.github/workflows/deploy.yml`** — на push в main (но этот пока-закомментирован, включим в Phase 9).

### 8. Документация для команды

Создать `CONTRIBUTING.md` в корне с разделами:
- Quickstart (make up → make migrate → открыть localhost:3000)
- Как добавить миграцию
- Как запустить тесты
- Правила Conventional Commits
- Ссылка на AGENTS.md и docs/

### 9. .gitignore и .dockerignore

Стандартные для Python + Node + Docker. Убедиться что не коммитится:
- `.env`
- `__pycache__`, `*.pyc`, `.venv`
- `node_modules`, `.next`
- `dump.sql`, `*.pem`, `*.key`

---

## Критерии готовности

- [ ] `make up` поднимает все сервисы, все они healthy
- [ ] `curl localhost:8000/health` → 200 OK
- [ ] `http://localhost:3000` показывает базовую страницу Next.js
- [ ] `http://localhost:8025` открывает MailHog
- [ ] `http://localhost:9001` открывает MinIO console
- [ ] `make migrate` проходит (пока без миграций — должен просто сказать «up-to-date»)
- [ ] CI на PR проходит (lint + test пустые, но структура есть)
- [ ] README / CONTRIBUTING понятен тому, кто впервые видит проект

---

## Что вернуть архитектору

В финальном ответе:
1. Список созданных файлов (верхнеуровневый)
2. Команды для верификации (что запустить)
3. Проблемы/отклонения, если были (например, версии библиотек пришлось занизить)
4. Рекомендации по Phase 1 (если что-то стоит учесть)
