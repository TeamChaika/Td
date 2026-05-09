# Phase 1 — Скелет приложений

**Цель:** создать базовые каркасы backend и frontend, которые дальше будут наполняться функционалом. Плюс — завести все модели БД и первую миграцию.

**Параллельные подзадачи:**
- 1a — Backend skeleton (`coder-backend`)
- 1b — Frontend skeleton (`coder-frontend`)
- 1c — DB models & migrations (`coder-backend`, параллельно с 1a)

**Зависит от:** Phase 0 завершена.
**Общий контекст:** `docs/ARCHITECTURE.md`, `docs/DATA_MODEL.md`, `docs/API_CONTRACT.md`.

---

## 1a. Backend Skeleton — `coder-backend`

### Задачи

**Структура пакета:**

```
backend/src/paytools/
├── __init__.py
├── main.py                # FastAPI app
├── core/
│   ├── __init__.py
│   ├── config.py          # pydantic-settings
│   ├── db.py              # async engine, session factory
│   ├── redis.py           # Redis client
│   ├── security.py        # JWT, password hashing, HMAC helpers
│   ├── tenancy.py         # current_organization context
│   ├── logging.py         # structlog setup
│   └── errors.py          # DomainError, error mapper
├── api/
│   ├── __init__.py
│   ├── deps.py            # FastAPI dependencies (get_db, current_user, ...)
│   ├── v1/
│   │   ├── __init__.py
│   │   ├── router.py      # главный роутер v1
│   │   ├── public/
│   │   │   └── __init__.py
│   │   ├── organizer/
│   │   │   └── __init__.py
│   │   ├── scanner/
│   │   │   └── __init__.py
│   │   ├── admin/
│   │   │   └── __init__.py
│   │   ├── webhooks/
│   │   │   └── __init__.py
│   │   └── schemas/
│   │       ├── __init__.py
│   │       └── common.py   # ErrorResponse, Pagination, etc.
├── db/
│   ├── __init__.py
│   ├── base.py            # Base = declarative_base с common mixins
│   ├── mixins.py          # UUIDPkMixin, TimestampsMixin, TenantMixin
│   └── models/            # наполняется в 1c
├── domain/
│   └── __init__.py
├── integrations/
│   └── __init__.py
└── workers/
    ├── __init__.py
    └── main.py            # arq WorkerSettings (пока пустой)
```

### `core/config.py`

Pydantic-settings класс `Settings` с полями из `.env.example`. Singleton через `@lru_cache`.

```python
class Settings(BaseSettings):
    database_url: PostgresDsn
    redis_url: RedisDsn
    secret_key: str = Field(min_length=32)
    fernet_key: str
    jwt_secret: str
    jwt_access_ttl_min: int = 15
    jwt_refresh_ttl_days: int = 30

    s3_endpoint: HttpUrl
    s3_bucket: str
    s3_access_key: str
    s3_secret_key: str
    s3_region: str = "ru-1"

    smtp_host: str
    smtp_port: int
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str
    smtp_tls: bool = True

    smsaero_email: str = ""
    smsaero_api_key: str = ""
    smsaero_sign: str = "TDPay"

    qrm_base_url: HttpUrl

    telegram_bot_token: str = ""

    platform_domain: str
    platform_commission_pct: float = 0.8

    enable_rate_limits: bool = False
    enable_captcha: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache
def get_settings() -> Settings: ...
```

### `core/db.py`

```python
engine = create_async_engine(settings.database_url, ...)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
```

### `core/security.py`

- `hash_password(password: str) -> str` — bcrypt
- `verify_password(password: str, hash: str) -> bool`
- `create_access_token(payload: dict) -> str` — JWT с exp
- `create_refresh_token(payload: dict) -> str`
- `decode_token(token: str) -> dict`
- `hmac_sign(data: str, secret: str) -> str`
- `hmac_verify(data: str, signature: str, secret: str) -> bool`
- `encrypt_secret(value: str) -> str` / `decrypt_secret(value: str) -> str` — Fernet

### `core/tenancy.py`

```python
# Context var для current organization
current_org_id: ContextVar[UUID | None] = ContextVar(...)

async def resolve_tenant_from_subdomain(host: str) -> Organization | None: ...
```

FastAPI middleware:
```python
class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Ищем X-Tenant-Slug или извлекаем из Host
        # Устанавливаем current_org_id
```

### `core/errors.py`

```python
class DomainError(Exception):
    code: str
    message: str
    status_code: int = 400

class NotFoundError(DomainError): status_code = 404
class ConflictError(DomainError): status_code = 409
class ForbiddenError(DomainError): status_code = 403
class PaymentError(DomainError): status_code = 502
# ...

# exception_handler преобразует DomainError → JSONResponse единого формата
```

### `main.py`

```python
app = FastAPI(title="TD Pay API", version="1.0.0")
app.add_middleware(TenantMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=[...], ...)
app.add_exception_handler(DomainError, domain_error_handler)
app.include_router(v1_router, prefix="/api/v1")

@app.get("/health")
async def health(): return {"status": "ok"}

@app.get("/ready")
async def ready(db: AsyncSession = Depends(get_session)):
    await db.execute(text("SELECT 1"))
    return {"status": "ok"}
```

### `api/deps.py`

- `get_session()` → `AsyncSession`
- `get_redis()` → Redis client
- `get_current_user()` → парсит JWT, возвращает User; 401 если нет/невалидный
- `require_role(*roles)` → dependency factory
- `get_current_organization()` → из current_user или context
- `get_idempotency_key()` → проверяет заголовок

### Критерии готовности (1a)

- [ ] `uvicorn paytools.main:app --reload` стартует без ошибок
- [ ] `curl /health` → 200
- [ ] `curl /ready` → 200 (подключается к БД)
- [ ] `curl /api/v1/` → 404 (роутер есть, но эндпоинтов пока нет)
- [ ] `curl /openapi.json` → валидный OpenAPI JSON
- [ ] Mypy strict проходит на src/
- [ ] Ruff без ошибок

---

## 1b. Frontend Skeleton — `coder-frontend`

### Задачи

**Структура:**

```
frontend/src/
├── app/
│   ├── layout.tsx                  # RootLayout с QueryProvider
│   ├── globals.css                 # Tailwind + shadcn vars
│   ├── middleware.ts               # Определение tenant по hostname
│   ├── (landing)/
│   │   ├── layout.tsx
│   │   └── page.tsx                # Лендинг tdpay.ru (заглушка)
│   ├── (tenant)/
│   │   ├── layout.tsx              # Загружает organization by subdomain
│   │   └── page.tsx                # Каталог (заглушка)
│   ├── admin/
│   │   ├── layout.tsx              # Sidebar + header
│   │   ├── login/page.tsx
│   │   └── page.tsx                # Dashboard (заглушка)
│   ├── scanner/
│   │   └── page.tsx                # Scanner (заглушка)
│   ├── platform/                    # Superadmin
│   │   └── page.tsx                 # (заглушка)
│   └── api/                         # Next.js route handlers (прокси?)
├── components/
│   ├── ui/                          # shadcn components
│   ├── brand/
│   │   ├── tenant-header.tsx
│   │   └── tenant-footer.tsx
│   └── providers/
│       └── query-provider.tsx
├── features/                        # наполняется в следующих фазах
├── lib/
│   ├── api/
│   │   ├── client.ts                # ofetch instance
│   │   └── types.ts                 # re-export из generated api.d.ts
│   ├── auth/
│   │   └── tokens.ts                # httpOnly cookie helpers (server-side)
│   ├── tenant/
│   │   └── resolve.ts               # getTenantBySlug (fetch из BE)
│   └── utils/
│       ├── cn.ts                    # clsx + tailwind-merge
│       ├── money.ts                 # format kopecks → "1 500 ₽"
│       └── date.ts                  # Intl + date-fns helpers
├── types/
│   └── api.d.ts                     # сгенерировано из OpenAPI
└── tests/
    └── setup.ts
```

### Middleware для tenant detection

`src/middleware.ts`:

```typescript
import { NextRequest, NextResponse } from 'next/server';

const PLATFORM_DOMAIN = process.env.NEXT_PUBLIC_PLATFORM_DOMAIN!;

export function middleware(req: NextRequest) {
  const host = req.headers.get('host') || '';
  const hostname = host.split(':')[0];

  // tdpay.ru или www.tdpay.ru → (landing)
  if (hostname === PLATFORM_DOMAIN || hostname === `www.${PLATFORM_DOMAIN}`) {
    return NextResponse.next();
  }

  // *.tdpay.ru → (tenant), добавляем заголовок
  if (hostname.endsWith(`.${PLATFORM_DOMAIN}`)) {
    const subdomain = hostname.replace(`.${PLATFORM_DOMAIN}`, '');
    const url = req.nextUrl.clone();
    url.pathname = `/(tenant)${url.pathname === '/' ? '' : url.pathname}`;
    const response = NextResponse.rewrite(url);
    response.headers.set('x-tenant-slug', subdomain);
    return response;
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!_next|api|favicon.ico|.*\\..*).*)'],
};
```

В dev: поддержать `localhost:3000` как `landing`, `{slug}.localhost:3000` как tenant (проверка по суффиксу).

### API client

`lib/api/client.ts`:

```typescript
import { ofetch } from 'ofetch';

export const api = ofetch.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
  credentials: 'include',
  onRequest({ options }) {
    // Добавлять X-Tenant-Slug если на tenant-странице
  },
  onResponseError({ response }) {
    // Маппинг ошибок
  }
});
```

### Скрипт генерации типов

В `package.json` уже есть `openapi:gen`. Запускаем после старта бэкенда → `src/types/api.d.ts` обновляется.

В CI: падать если сгенерированные типы отличаются от закоммиченных.

### shadcn/ui темизация

Dark-theme as default (согласно ответу «свой дизайн», пока минималистичный dark). В `globals.css`:

```css
@layer base {
  :root {
    /* Primary: brand TD Pay — ещё не определён, пока blue-500 */
    --primary: 217 91% 60%;
    --primary-foreground: 0 0% 100%;
    /* ... */
  }
  .dark {
    /* ... */
  }
}
```

Поддержка брендирования от организатора: CSS variables, которые переопределяются в `(tenant)/layout.tsx` из `organization.brand_color`.

### Критерии готовности (1b)

- [ ] `pnpm dev` стартует на :3000 без ошибок
- [ ] `http://localhost:3000` открывает лендинг-заглушку
- [ ] `http://acme.localhost:3000` открывает tenant-заглушку (можно добавить `/etc/hosts` запись)
- [ ] `http://localhost:3000/admin/login` открывает страницу логина (заглушка)
- [ ] `http://localhost:3000/scanner` открывает scanner-заглушку
- [ ] `http://localhost:3000/platform` открывает platform-заглушку
- [ ] ESLint без ошибок
- [ ] `tsc --noEmit` без ошибок
- [ ] shadcn установлен, есть button/input/form/card — можно импортить
- [ ] `pnpm openapi:gen` работает (когда BE запущен)

---

## 1c. DB Models & Migrations — `coder-backend` (параллельно с 1a)

### Задачи

Создать все модели из `docs/DATA_MODEL.md` в `backend/src/paytools/db/models/`.

**Файлы:**

```
db/models/
├── __init__.py            # re-export всех моделей
├── organization.py        # Organization
├── user.py                # User
├── customer.py            # Customer (v1.0, но таблица создаётся сразу)
├── event.py               # Event, Tariff
├── reservation.py         # Reservation, ReservationItem
├── ticket.py              # Ticket
├── payment.py             # Payment
├── promocode.py           # PromoCode, PromoCodeUsage
├── billing.py             # OrganizationBalance, BalanceTransaction
├── deposit.py             # Deposit, DepositTransaction (schema готова, но не используется в MVP)
├── system.py              # WebhookDelivery, AuditLog, EmailBlocklist
└── enums.py               # Все ENUM-ы (через PgEnum или text + CHECK)
```

### Miksiny

`db/mixins.py`:

```python
class UUIDPkMixin:
    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=lambda: uuid_utils.uuid7()  # sortable by time
    )

class TimestampsMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False
    )

class TenantMixin:
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
```

### ENUM-ы

Используем PostgreSQL ENUM через SQLAlchemy:

```python
from sqlalchemy.dialects.postgresql import ENUM

OrganizationStatus = ENUM(
    "pending_moderation", "active", "suspended",
    name="organization_status", create_type=True
)
```

Все ENUM-ы из `DATA_MODEL.md` — в `enums.py`.

### Пример модели

```python
# db/models/event.py

class Event(Base, UUIDPkMixin, TimestampsMixin, TenantMixin):
    __tablename__ = "events"

    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description_md: Mapped[str | None] = mapped_column(Text)
    location_name: Mapped[str | None] = mapped_column(String(255))
    location_address: Mapped[str | None] = mapped_column(Text)
    schedule: Mapped[dict] = mapped_column(JSONB, nullable=False)
    capacity_policy: Mapped[dict] = mapped_column(JSONB, nullable=False)
    sold_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    image_card_url: Mapped[str | None] = mapped_column(Text)
    image_background_url: Mapped[str | None] = mapped_column(Text)
    custom_fields_schema: Mapped[list | None] = mapped_column(JSONB)
    status: Mapped[EventStatusType] = mapped_column(EventStatus, nullable=False, server_default="draft")
    moderation_note: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_events_org_slug"),
        Index("ix_events_org_status", "organization_id", "status"),
    )
```

### Alembic baseline миграция

После создания всех моделей:

```bash
docker compose exec backend alembic revision --autogenerate -m "baseline"
```

**ВАЖНО:** отревьюить сгенерированную миграцию — часто:
- Alembic не всегда корректно определяет ENUM, может понадобиться ручная правка
- Проверить индексы
- Проверить ON DELETE RESTRICT
- Проверить server_default для timestamps

Миграция должна идемпотентно проходить на чистой БД.

### Репозитории (базовый)

`db/repositories/base.py`:

```python
class BaseRepository(Generic[ModelType]):
    model: type[ModelType]

    def __init__(self, session: AsyncSession, organization_id: UUID | None = None):
        self.session = session
        self.organization_id = organization_id

    def _apply_tenant_filter(self, stmt):
        """Автоматически фильтровать по organization_id, если модель tenant."""
        if self.organization_id and hasattr(self.model, "organization_id"):
            stmt = stmt.where(self.model.organization_id == self.organization_id)
        return stmt

    async def get(self, id: UUID) -> ModelType | None: ...
    async def list(self, **filters) -> list[ModelType]: ...
    async def create(self, **data) -> ModelType: ...
    async def update(self, instance: ModelType, **data) -> ModelType: ...
    async def delete(self, instance: ModelType) -> None: ...
```

### Критерии готовности (1c)

- [ ] Все модели из DATA_MODEL.md созданы
- [ ] Все ENUM объявлены
- [ ] `alembic revision --autogenerate` не генерирует новых изменений (schema синхронна)
- [ ] `alembic upgrade head` проходит на пустой БД
- [ ] `alembic downgrade base` проходит
- [ ] Базовый репозиторий работает (демо в unit-тесте)
- [ ] Mypy strict проходит

---

## Что вернуть архитектору (от каждого)

**coder-backend (1a + 1c):**
1. Список созданных файлов
2. Скриншот `openapi.json` структуры (верхний уровень paths)
3. Результат `alembic upgrade head` в dev-БД
4. Отклонения от DATA_MODEL.md если были
5. Рекомендации для Phase 2

**coder-frontend (1b):**
1. Список созданных страниц
2. Скриншот главной и tenant-страницы
3. Как воспроизвести локально (`/etc/hosts` или альтернатива)
4. Рекомендации для Phase 2
