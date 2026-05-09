# Phase 8 — PWA Scanner

**Цель:** контролёр на входе сканирует QR билета через мобильный браузер, видит результат «валидный / уже использован / отменён», показывает имя гостя.

**Онлайн-only в MVP.** Офлайн — в v1.1.

**Параллельные подзадачи:**
- 8a — Backend scanner API (`coder-backend`)
- 8b — Frontend PWA (`coder-frontend`)
- 8c — Tests (`coder-tests`)

**Зависит от:** Phase 5 (tickets), Phase 2 (auth).
**Референсы:** `API_CONTRACT.md § 4`, `ARCHITECTURE.md § 6`.

---

## 8a. Backend — `coder-backend`

### Endpoints

Все требуют JWT с `role in (organizer, scanner, cashier)`.

- **`GET /api/v1/scanner/events/today`** — события организации с датой сегодня (учёт schedule type: single / sessions / period). Отсортированы по времени.

- **`POST /api/v1/scanner/events/{id}/activate`** — фиксирует в Redis «сканер-сессия X работает над событием Y». Key: `scanner:{user_id}:active_event`, TTL 24h. Для контекста в UI.

- **`POST /api/v1/scanner/check-in`**:
  - Body: `{qr_payload?: string, code?: string, event_id: UUID}`
  - Логика:
    1. Если qr_payload — разбираем `{ticket_id}.{signature}`, проверяем HMAC.
    2. Если code — ищем по `tickets.code` (uniq).
    3. Валидируем: ticket exists, organization_id == current user's org, event_id соответствует выбранному (если не совпадает — возвращаем `wrong_event` **не меняя** ticket).
    4. SELECT FOR UPDATE ticket.
    5. Проверка статуса:
       - `issued` → **check-in**, status=`checked_in`, сохранить `checked_in_at`, `checked_in_by_user_id`
       - `checked_in` → result `already_used` с показом `checked_in_at`
       - `cancelled` / `refunded` → result `cancelled`
    6. Ответ содержит: result, ticket (guest data, tariff, is_complimentary), event (title), checked_in_at
    7. Audit log
  - Возвращает 200 OK всегда (в теле — структура с `result`), сканер уже сам показывает разный UI.

- **`POST /api/v1/scanner/uncheck-in`** (для откатов):
  - Body: `{ticket_id, reason}`
  - Только если в последние 5 минут был check-in этим пользователем
  - Возвращает статус в `issued`
  - Audit log

- **`GET /api/v1/scanner/events/{id}/stats`**:
  - `{total_issued: int, checked_in: int, checked_in_percent: float}`
  - Для polling в UI

### Concurrency

Используем `SELECT ... FOR UPDATE` с `NOWAIT`:

```python
ticket = await session.execute(
    select(Ticket).where(Ticket.id == ticket_id).with_for_update(nowait=True)
)
```

Если два сканера одновременно — второй получит ошибку lock, retry не делаем, сразу отвечаем `already_used` (в 99% случаев первый уже закоммитил).

### Критерии готовности (8a)

- [ ] Check-in работает, race-condition тест проходит
- [ ] Стат-endpoint корректен
- [ ] Uncheck-in с таймлимитом 5 минут
- [ ] Tenant isolation: сканер org A не может сканировать билеты org B

---

## 8b. Frontend — `coder-frontend`

### PWA setup

`frontend/src/app/scanner/` + `public/manifest.json`:

```json
{
  "name": "TD Pay Scanner",
  "short_name": "TDScan",
  "start_url": "/scanner",
  "display": "standalone",
  "theme_color": "#0f172a",
  "background_color": "#0f172a",
  "orientation": "portrait",
  "icons": [...]
}
```

Service worker (опционально в MVP — достаточно manifest.json + apple-touch-icon для «добавить на главный экран»).

### Страницы

1. **`/scanner/login`** — отдельный login (не через /admin):
   - Email + password только
   - После логина проверяется роль (не организатор/сканер/кассир → redirect в /admin)

2. **`/scanner`** — главная:
   - Если не выбрано событие на сегодня: список сегодняшних событий → выбор
   - Если выбрано: переход к `/scanner/scan`

3. **`/scanner/scan`**:
   - Header: название события, счётчик «5 / 200», кнопка «Сменить событие»
   - Основной блок — камера через `html5-qrcode` или `@zxing/browser`
   - Кнопка «Ввести код вручную» → input-field для `code` (типа ABC12345)
   - После скана — overlay с результатом:
     - **Валидный (issued → checked_in):** зелёный, ✓, имя гостя, тариф, `guest_index`, звук OK, vibrate 200ms
     - **Уже использован:** жёлтый, ⚠, имя + «Пришёл в 19:42», звук warning, vibrate 2×100ms
     - **Отменённый:** красный, ✗, причина, звук error, vibrate 500ms
     - **Чужое событие:** красный, «Билет на другое событие: {title}»
     - **Неверный QR:** красный, «Некорректный QR-код»
   - После 3 сек overlay исчезает, сканер снова активен
   - Кнопка «Отменить последний check-in» — появляется 5 минут после успешного скана

4. **`/scanner/manual-entry`** — ручной ввод кода, отдельная страница на случай если QR не считывается.

### Audio

`public/sounds/`:
- `ok.mp3` — короткий «бип» (успех)
- `warn.mp3` — средний тон (уже использован)
- `err.mp3` — низкий тон (ошибка)

Воспроизведение через Web Audio API или просто `<audio>` tag.

### Vibration

```javascript
navigator.vibrate?.(200);
```

### Polling stats

Компонент `<ScannerStatsBar>` — раз в 10 сек тянет `/scanner/events/{id}/stats`, показывает счётчик.

### Offline handling (в MVP)

Если нет сети → показываем «Нет интернета» + кнопку «Повторить». Сам сканер работает, но чек-ин не отправляется (показываем error overlay).

### Critical UX

- **Камера должна включиться автоматически** (prompt для permission)
- Работает в **портретной ориентации**
- Большая зона для QR (square overlay)
- **Fullscreen-режим** опционально (`document.fullscreenElement`)
- На iOS Safari — камера работает только в standalone-режиме (PWA) или в браузере напрямую (не в WebView)

### Критерии готовности (8b)

- [ ] PWA устанавливается на iOS/Android («Добавить на главный экран»)
- [ ] Камера включается
- [ ] Сканирование QR работает
- [ ] Все состояния результата показываются корректно
- [ ] Звук + вибрация работают
- [ ] Stats bar обновляется
- [ ] Ручной ввод кода работает

---

## 8c. Tests

### Unit

- `TicketService.check_in`: все переходы + race
- QR payload verify: правильная/подделанная подпись

### Integration

- Полный сценарий: создать event → купить билет → сканер logins → activates event → check-in → second scan = already_used

### E2E (Playwright)

- На mobile viewport: открыть /scanner → залогиниться → выбрать событие → имитировать скан (через ручной ввод кода, т.к. реальная камера в CI не работает) → проверить все состояния

---

## Что вернуть

Скриншоты (желательно с мобильного) + видео процесса сканирования
