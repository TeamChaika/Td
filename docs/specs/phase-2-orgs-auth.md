# Phase 2 — Organizations & Auth

**Цель:** организаторы могут зарегистрироваться, залогиниться, суперадмин может их одобрить. Полная изоляция данных между организациями.

**Параллельные подзадачи:**
- 2a — Backend auth + organizations (`coder-backend`)
- 2b — Frontend register/login/admin shell (`coder-frontend`)
- 2c — Tests (`coder-tests`)

**Зависит от:** Phase 1.
**Референсы:** `ARCHITECTURE.md § 1.1, 4.1`, `API_CONTRACT.md § 3`, `DATA_MODEL.md § 1`.

---

## 2a. Backend — `coder-backend`

### Domain services

`domain/organizations/service.py`:

- `OrganizationService.register(data) → Organization` — создаёт организацию со статусом `pending_moderation` и первого пользователя-owner с ролью `organizer`. Отправляет нотификацию superadmin'ам (через arq задачу, пока-заглушка).
- `OrganizationService.approve(org_id, by_user) → Organization` — переводит в `active`. Только superadmin. Пишет в audit_log.
- `OrganizationService.suspend(org_id, by_user, reason)` → `suspended`.
- `OrganizationService.get_by_slug(slug)` — для tenant middleware.
- `OrganizationService.update_settings(org_id, data)` — бренд, SMTP, QRM-ключ (зашифровать!), Telegram chat.

`domain/auth/service.py`:

- `AuthService.signup_organization(email, password, first_name, last_name, org_name, org_slug)` → создаёт Organization + User(role=organizer) атомарно. Валидация slug (латиница + цифры + дефис, 3..64 символа, не в зарезервированном списке).
- `AuthService.login(email, password) → TokenPair`
- `AuthService.request_magic_link(email)` — генерирует короткоживущий токен (15 мин), сохраняет в Redis (`magic:{token} → email`), отправляет email через arq-задачу.
- `AuthService.verify_magic_link(token) → TokenPair`
- `AuthService.refresh(refresh_token) → TokenPair`
- `AuthService.logout(refresh_token)` — блок-лист в Redis.

Password policy: min 10 символов, bcrypt rounds=12.

### Reserved slugs

Запретить slug-и: `www`, `admin`, `api`, `platform`, `scanner`, `app`, `mail`, `support`, `help`, `docs`, `blog`, `static`, `assets`, `cdn`.

### API endpoints

**Публичные:**
- `POST /api/v1/public/organizations/register` — регистрация
- `GET /api/v1/public/tenant/resolve?slug=acme` — для middleware фронта (получить brand_name, logo, brand_color, status)

**Auth:**
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/magic-link/request`
- `POST /api/v1/auth/magic-link/verify`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`

**Organizer:**
- `GET /api/v1/organizer/organization`
- `PATCH /api/v1/organizer/organization` — поля бренда, QRM (шифрование), SMTP, Telegram
- `POST /api/v1/organizer/organization/qrm/test` — вызывает QRM `GET /users/check-api-key/`, возвращает результат

**Admin:**
- `GET /api/v1/admin/organizations?status=pending_moderation`
- `POST /api/v1/admin/organizations/{id}/approve`
- `POST /api/v1/admin/organizations/{id}/suspend`

### JWT payload

```json
{
  "sub": "user_id_uuid",
  "org": "organization_id_uuid_or_null",
  "role": "organizer",
  "type": "access",
  "exp": 1234567890,
  "jti": "unique_id"
}
```

Refresh token — в httpOnly secure cookie `tdpay_refresh`, path=/api/v1/auth, SameSite=Lax.

### Tenant middleware

Обновить `core/tenancy.py` из Phase 1:

1. Для публичных роутов: читать `X-Tenant-Slug` или Host → резолвить org → ставить в context.
2. Для organizer-роутов: читать из JWT → ставить в context.
3. Если organizer пытается работать с чужой org (через query/body) → 403.

### Безопасность

- **Шифрование** `qrm_api_key` через Fernet (функции уже есть в security.py).
- Webhook / endpoint для регистрации — **не запрашивать** `qrm_api_key` сразу, его заносим через отдельный `PATCH` когда организация уже `active`.
- Логи: не логируем пароли, токены, QRM-ключи (фильтры в structlog).
- Email-validator проверяет формат + MX-запись (опционально для MVP).
- Email blocklist check (если попал в `email_blocklist` → 400).

### Критерии готовности (2a)

- [ ] Все 9 endpoints реализованы и документированы
- [ ] Password hashing работает
- [ ] JWT создаётся/валидируется
- [ ] Magic-link flow работает через mailhog
- [ ] QRM key сохраняется зашифрованным, проверка /check-api-key работает (на тестовом ключе)
- [ ] Tenant isolation: организатор A не может получить/изменить данные организации B
- [ ] Slug validation (латиница, не в reserved)
- [ ] Audit log пишет approve/suspend события
- [ ] Mypy strict + ruff

---

## 2b. Frontend — `coder-frontend`

### Страницы

1. **`tdpay.ru/register`** — форма регистрации организатора:
   - Поля: email, password (+confirm), first_name, last_name, organization_name, organization_slug (с live-проверкой доступности), checkbox «согласен с политикой и офертой»
   - Slug-поле: показывать превью `{slug}.tdpay.ru`
   - После submit: «Заявка отправлена на модерацию, мы свяжемся с вами»

2. **`tdpay.ru/admin/login`** — форма логина:
   - Email + password
   - Ссылка «Получить ссылку для входа» → magic-link flow
   - Кнопка Telegram Login — **заглушка с disabled tooltip "Скоро"** (реальный flow — v1.0)

3. **`tdpay.ru/admin/magic-link`** — страница приёма magic-link token из URL, автоматический verify → редирект в /admin

4. **`tdpay.ru/admin`** — dashboard layout (защищён auth middleware):
   - Sidebar: Dashboard / События / Тарифы / Промокоды / Брони / Билеты / Настройки / Биллинг
   - Header: имя пользователя, organization name, logout
   - Если organization.status=pending_moderation — показать баннер «На модерации»
   - Если status=suspended — показать блокирующий экран «Аккаунт заблокирован»
   - Главная заглушка (dashboard наполним в Phase 3+)

5. **`tdpay.ru/admin/settings`** — настройки организации:
   - Таб **Бренд**: logo upload (drag-n-drop), brand_color picker, brand_name
   - Таб **Реквизиты**: legal_entity_type, inn, legal_name, legal_address
   - Таб **Платежи**: qrm_api_key (password-input), qrm_api_login, кнопка "Проверить ключ"
   - Таб **Email**: кастомный SMTP (пока заглушка, v1.0)
   - Таб **Telegram**: telegram_chat_id (инструкция «добавьте @TDPayBot в чат и пришлите /id» — пока заглушка)
   - Таб **Контакты и возвраты**: contact_email, contact_phone, refund_policy (textarea)

6. **`tdpay.ru/platform`** — суперадмин (layout):
   - Отдельный login route `/platform/login`
   - Sidebar: Организации / Модерация событий / Биллинг / Аудит
   - Страница «Организации»: таблица с фильтром по статусу, actions: Approve, Suspend, View

### Auth на фронте

`lib/auth/`:
- `useSession()` — хук, возвращает {user, organization, loading}, тянется из `/api/v1/auth/me`
- `useLogin()`, `useLogout()`, `useRegister()` — мутации
- Access token — в памяти (не в localStorage!). Refresh token — в httpOnly cookie, невидим JS.
- На запрос 401 → пробуем `/auth/refresh` → retry оригинальный запрос → если и refresh 401 → logout + redirect на login.

### Защита роутов

`middleware.ts` расширить:
- `/admin/*` (кроме `/admin/login`, `/admin/magic-link`) — проверка наличия refresh cookie, иначе redirect на login
- `/platform/*` (кроме `/platform/login`) — аналогично, плюс роль superadmin

### Форма регистрации — детали UX

- Slug live-check через debounced fetch
- Pass strength indicator
- Ошибки inline у каждого поля
- После submit: CTA «Открыть почту» (autodetect Gmail/Yandex/etc) + таймер «Мы отправили письмо с подтверждением»

### Критерии готовности (2b)

- [ ] Регистрация работает, пользователь попадает на «на модерации»
- [ ] Login email+password работает
- [ ] Magic-link flow: запрос → письмо в mailhog → переход по ссылке → залогинен
- [ ] Admin layout защищён
- [ ] Settings сохраняют данные, включая QRM-ключ (с проверкой)
- [ ] Platform layout работает для superadmin, approve выводит организацию в active
- [ ] Все формы валидируются через Zod
- [ ] Responsive (mobile работает)
- [ ] Типы сгенерированы из OpenAPI (`pnpm openapi:gen`)

---

## 2c. Tests — `coder-tests`

### Unit

- `AuthService.hash_password / verify_password` — правильный bcrypt
- `AuthService.create_access_token / decode` — включая exp, неверная подпись
- `OrganizationService.register` — создаёт org+user атомарно, откатывает при ошибке
- `slug_validator` — все edge cases (короткий/длинный/запрещённый/с спецсимволами)

### Integration (pytest + httpx.AsyncClient + testcontainers или testing DB)

- `POST /public/organizations/register` — 201, создаёт запись
- Дубль email → 409
- Дубль slug → 409
- Зарезервированный slug → 422
- `POST /auth/login` — корректный → 200 с токенами
- Неверный пароль → 401
- `POST /auth/magic-link/request` — всегда 202, в тесте проверяем что в Redis появился токен
- `POST /auth/magic-link/verify` — валидный токен → 200, токен удаляется из Redis
- `POST /admin/organizations/{id}/approve` — от superadmin: 200, статус меняется
- От organizer: 403
- `PATCH /organizer/organization` — обновляется, qrm_api_key при чтении снова не возвращается в ответе (только masked)
- **Tenant isolation**: org A создаёт событие, organizer B запрашивает его → 404

### E2E (Playwright, минимум)

- Регистрация → видит «на модерации»
- Логин после approval → видит dashboard

### Критерии готовности (2c)

- [ ] Coverage `domain/auth/` и `domain/organizations/` ≥ 85%
- [ ] Все integration-сценарии зелёные
- [ ] Есть хотя бы 1 E2E проходящий на CI

---

## Что вернуть архитектору

**coder-backend:** список endpoints + примеры curl-запросов + скриншот Swagger /docs

**coder-frontend:** скриншоты всех страниц + как протестировать локально

**coder-tests:** результаты coverage + список нерешённых кейсов если есть
