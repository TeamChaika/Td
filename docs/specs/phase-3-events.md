# Phase 3 — Events & Tariffs

**Цель:** организатор создаёт события с тарифами, управляет ими, гость видит каталог.

**Параллельные подзадачи:**
- 3a — Backend CRUD + S3 upload (`coder-backend`)
- 3b — Frontend admin wizard (`coder-frontend`)
- 3c — Frontend публичная витрина (`coder-frontend`, параллельно)
- 3d — Tests (`coder-tests`)

**Зависит от:** Phase 2.
**Референсы:** `DATA_MODEL.md § 2`, `API_CONTRACT.md § 1, 3`.

---

## 3a. Backend — `coder-backend`

### Domain

`domain/events/service.py`:

- `EventService.create(org_id, data) → Event` — создаёт в статусе `draft`.
- `EventService.update(event_id, data)` — только если draft или published (разные разрешённые поля).
- `EventService.submit_for_moderation(event_id)` — draft → pending_moderation.
- `EventService.publish(event_id, by_user)` — pending_moderation → published. Superadmin, или organizer если `organization.auto_publish_enabled=true`.
- `EventService.reject(event_id, note)` — pending → rejected.
- `EventService.archive(event_id)` — soft-delete.
- `EventService.upload_image(event_id, file, kind='card'|'background')` → uploads to S3 via integrations/storage, возвращает URL.
- `EventService.list_public(org_id, filters)` — только published, сортировка по `schedule.starts_at`.

**Валидация:**
- `schedule` — Pydantic discriminated union по `type`. Проверка дат (end > start, не в прошлом).
- `capacity_policy` — union по `type`. Если `per_tariff`, то хотя бы один тариф должен иметь `capacity_limit`.
- `custom_fields_schema` — список с ограничением 10 полей, каждый с уникальным `id`.
- `slug` — генерация auto из title + uniq check, или принимаем от пользователя (latin, dashes).

`domain/tariffs/service.py`:

- `TariffService.create(event_id, data)` — валидация: event в статусе draft или published, price ≥ 0 (для complimentary может быть 0).
- `TariffService.update(tariff_id, data)` — запретить менять `price_kopecks` если уже есть проданные билеты (можно создать новый тариф).
- `TariffService.delete(tariff_id)` — soft через `is_active=false`, если есть проданные билеты.

### API

Реализовать все `POST/GET/PATCH/DELETE /api/v1/organizer/events[/*]` и `/tariffs` из `API_CONTRACT.md § 3`.

Публичные:
- `GET /api/v1/public/events` — список published событий current organization
- `GET /api/v1/public/events/{slug}` — детали + тарифы + custom_fields_schema

**S3 upload:**

`integrations/storage/s3.py`:
- Использовать `aioboto3` или `boto3 + asyncio.to_thread`
- Pre-signed upload flow: фронт получает pre-signed URL, загружает напрямую в S3, потом отправляет URL на бэк
- Или прямой upload через бэкенд (проще в MVP, возьмём этот вариант)
- Валидация: image/jpeg, image/png, image/webp; max 5MB; resize до 1920x1080 через Pillow

### Критерии готовности (3a)

- [ ] CRUD events работает через Swagger
- [ ] S3 upload работает (локально через MinIO)
- [ ] Публикация событий проходит через статусы корректно
- [ ] Публичные endpoints работают (с tenant middleware)
- [ ] Валидация всех JSON-полей
- [ ] Tenant isolation: organizer A не видит events B

---

## 3b. Frontend admin — `coder-frontend`

### Страницы

1. **`/admin/events`** — список:
   - Таблица: название, дата, тариф «от», продано/всего, статус
   - Фильтры: статус, период
   - Кнопка «+ Создать событие» → wizard

2. **`/admin/events/new`** — wizard в 3 шага:
   - **Шаг 1. Основное**: title, slug (auto-preview), description_md (простой textarea с Markdown hints), location_name, location_address, schedule type + поля, image_card + image_background upload
   - **Шаг 2. Тарифы**: список тарифов (inline add/edit/remove), для каждого: name, description, price, capacity_limit, is_active. Валидация: хотя бы 1 тариф, суммы capacity ≥ 0. Выбор capacity_policy: total / per_tariff / hybrid / unlimited (влияет на показ capacity_limit полей).
   - **Шаг 3. Поля формы**: добавление custom fields (id, label, type, required, options для select). Preview формы брони.
   - Внизу каждого шага: «Назад / Далее / Сохранить черновик».
   - Итоговый шаг: «Отправить на модерацию» или «Сохранить черновик».

3. **`/admin/events/{id}`** — редактирование — тот же wizard, но с предзаполнением.

4. **`/admin/events/{id}/preview`** — preview как на витрине.

### Компоненты

- `<ScheduleEditor>` — переключалка type single/sessions/period
- `<CapacityPolicyEditor>`
- `<CustomFieldsEditor>` — drag-n-drop для reorder (в MVP можно простой UP/DOWN)
- `<ImageUpload>` — с preview, кроп опционально (в MVP без кропа)
- `<TariffRow>` — inline форма тарифа

### Критерии готовности (3b)

- [ ] Wizard проходится от начала до конца
- [ ] Черновик сохраняется между шагами
- [ ] Все валидации отображаются inline
- [ ] Preview показывает как будет выглядеть на витрине
- [ ] Upload картинок работает

---

## 3c. Frontend витрина — `coder-frontend` (параллельно с 3b)

### Страницы на `{slug}.tdpay.ru`

1. **`/` (каталог)** — список карточек:
   - Каждая карточка: background image + title + дата + price_from
   - Hover-эффекты
   - Фильтры (date range) — в MVP минимум, просто сортировка

2. **`/events/{slug}`** — детали события:
   - Hero: background image + title + дата/время/место
   - Описание (Markdown → HTML через react-markdown)
   - Список тарифов с ценами
   - Sticky-кнопка «Купить билет» → `/events/{slug}/book`

3. **`/about`**, **`/contacts`**, **`/terms`** (оферта), **`/privacy`** — статические страницы из organization settings (refund_policy, contact_email и т.д.)

### Брендинг

Layout `(tenant)` читает organization.brand_color → подставляет в CSS var `--primary`. Logo в header, brand_name в title.

### Критерии готовности (3c)

- [ ] Каталог показывает только published события current org
- [ ] Страница события показывает всё нужное
- [ ] Брендинг применяется
- [ ] SEO: `<title>`, `<meta description>` с данными события
- [ ] SSG/ISR (revalidate 60s) — для скорости

---

## 3d. Tests — `coder-tests`

### Unit/Integration

- `EventService.create` — все статусы, валидации
- Schedule validator — все 3 типа, граничные случаи
- CapacityPolicy validator
- CustomFields schema validator
- `TariffService` — запрет изменения цены при проданных билетах
- API CRUD tests (org A vs org B)
- S3 upload integration test (с MinIO)

### E2E (минимум 2 сценария)

- Organizer: создаёт событие → модерация → публикация → видно на витрине
- Guest: открывает витрину → видит карточки → переходит в детали

---

## Что вернуть

**coder-backend:** curl-примеры всех endpoints + скриншот создания события и картинки в S3

**coder-frontend:** скриншоты wizard'а и витрины + видео прохождения (опционально)

**coder-tests:** coverage отчёт
