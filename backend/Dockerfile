# Многостадийная сборка: dev и prod

# --- base: общие зависимости для сборки ---
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Системные зависимости: нужны weasyprint (pango/cairo), psycopg/asyncpg и сборка колес
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libcairo2 \
    libffi-dev \
    curl \
 && rm -rf /var/lib/apt/lists/*

# uv — быстрый менеджер пакетов
RUN pip install --no-cache-dir uv

WORKDIR /app

# --- dev: устанавливаем dev-зависимости и запускаем с --reload ---
FROM base AS dev

# Сначала только pyproject.toml — для кэша слоя зависимостей
COPY pyproject.toml ./
# Создаём пустой README, так как uv может его искать
RUN touch README.md

# Ставим зависимости в системный site-packages (без venv для простоты в контейнере)
RUN uv pip install --system --no-cache \
    "fastapi>=0.115" "uvicorn[standard]>=0.32" \
    "sqlalchemy[asyncio]>=2.0.36" "asyncpg>=0.30" "alembic>=1.14" \
    "pydantic>=2.10" "pydantic-settings>=2.7" \
    "redis>=5.2" "arq>=0.26" "httpx>=0.28" \
    "aiosmtplib>=3.0" "jinja2>=3.1" "weasyprint>=63" \
    "uuid-utils>=0.10" "bcrypt>=4.2" "pyjwt[crypto]>=2.10" "cryptography>=44" \
    "structlog>=24.4" "python-multipart>=0.0.18" \
    "boto3>=1.35" "openpyxl>=3.1" "qrcode[pil]>=8.0" "email-validator>=2.2" \
    "pytest>=8.3" "pytest-asyncio>=0.25" "pytest-cov>=6.0" \
    "ruff>=0.8" "mypy>=1.13" "types-redis"

# Код приложения монтируется volume'ом в docker-compose, поэтому в образе достаточно структуры
COPY src/paytools ./paytools
COPY alembic.ini ./
COPY alembic ./alembic

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "paytools.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# --- prod: минимальный образ для продакшна ---
FROM base AS prod

COPY pyproject.toml ./
RUN touch README.md

COPY src/paytools ./paytools
COPY alembic.ini ./
COPY alembic ./alembic

# Только runtime-зависимости
RUN uv pip install --system --no-cache \
    "fastapi>=0.115" "uvicorn[standard]>=0.32" \
    "sqlalchemy[asyncio]>=2.0.36" "asyncpg>=0.30" "alembic>=1.14" \
    "pydantic>=2.10" "pydantic-settings>=2.7" \
    "redis>=5.2" "arq>=0.26" "httpx>=0.28" \
    "aiosmtplib>=3.0" "jinja2>=3.1" "weasyprint>=63" \
    "uuid-utils>=0.10" "bcrypt>=4.2" "pyjwt[crypto]>=2.10" "cryptography>=44" \
    "structlog>=24.4" "python-multipart>=0.0.18" \
    "boto3>=1.35" "openpyxl>=3.1" "qrcode[pil]>=8.0" "email-validator>=2.2"

# Запускаем под непривилегированным пользователем
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "paytools.main:app", "--host", "0.0.0.0", "--port", "8000"]
