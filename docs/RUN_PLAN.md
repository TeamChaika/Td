# TD Pay — План запуска подагентов

Этот документ — **оперативный план**. Описывает, как архитектор (я) запускает кодеров для MVP. Каждая строка — одна команда.

---

## Общие правила

1. **Параллелизм** обозначается `‖`. Такие задачи запускаются одним сообщением с несколькими вызовами `task`.
2. Каждая задача = 1 spec-файл из `docs/specs/`.
3. После завершения группы параллельных задач → **checkpoint**: архитектор интегрирует результаты и решает, готовы ли мы идти дальше.
4. После **каждой фазы** (кроме Phase 0) — запуск `reviewer` на полную проверку перед переходом к следующей.
5. Кодерам всегда в промпте передаём ссылку на spec-файл + ARCHITECTURE.md + DATA_MODEL.md + API_CONTRACT.md.
6. Если кодер просит уточнение — архитектор отвечает в той же task-сессии (через `task_id`).

---

## Порядок выполнения

### Phase 0 — Bootstrap (1 задача, ~1 итерация)

```
→ devops: docs/specs/phase-0-bootstrap.md
```

**Выход:** работающий docker-compose, скелеты backend/frontend, CI, документация.

---

### Phase 1 — Скелет (3 параллельные задачи, 1 итерация)

```
→ coder-backend: 1a skeleton     ‖ coder-frontend: 1b skeleton     ‖ coder-backend: 1c models+migration
```

**Выход:** обе части запускаются, модели БД созданы, миграция применена.

**Checkpoint:** архитектор проверяет:
- Ключи/структура в `paytools/core/config.py` соответствует `.env.example`
- Все модели из DATA_MODEL.md созданы
- Frontend middleware детектит tenant корректно
- OpenAPI генерируется

**Review:** `reviewer` после checkpoint'а.

---

### Phase 2 — Organizations & Auth (3 параллельные задачи)

```
→ coder-backend: 2a auth+orgs   ‖ coder-frontend: 2b register/login    ‖ coder-tests: 2c auth tests
```

**Зависимости:** 2b ждёт минимального бэкенда из 2a (хотя бы OpenAPI-схемы) — в идеале 2a стартует чуть раньше.

**Выход:** рабочий signup + login + magic-link + tenant isolation + superadmin approve.

**Review.**

---

### Phase 3 — Events & Tariffs (4 параллельные задачи)

```
→ coder-backend: 3a CRUD+S3   ‖ coder-frontend: 3b admin wizard   ‖ coder-frontend: 3c витрина   ‖ coder-tests: 3d
```

**Примечание:** 3b и 3c оба фронтовые, но не пересекаются (admin vs tenant), можно дать одному coder-frontend последовательно или двум вызовам одного типа агента параллельно (OpenCode это позволяет).

**Выход:** организатор создаёт события, гость видит каталог.

**Review.**

---

### Phase 4 — Booking & Promo (3 параллельные задачи)

```
→ coder-backend: 4a   ‖ coder-frontend: 4b форма   ‖ coder-tests: 4c
```

**Выход:** бронь работает до этапа «ожидание оплаты», промокоды применяются.

**Review.**

---

### Phase 5 — Payments QRM + Tickets (4 задачи, частично последовательно)

```
Шаг 1: → coder-backend: 5a QRM provider + payment service
Шаг 2 (после 5a): → coder-backend: 5b ticket gen  ‖  coder-frontend: 5c pay/ticket pages  ‖  coder-tests: 5d
```

5b зависит от 5a (использует Payment domain). 5c можно стартовать параллельно с 5b, т.к. на фронте нужны только API-контракты из 5a.

**Выход:** полный цикл «купил → оплатил → получил билет».

**Это самый критичный этап.** Надо провести **Manual QA-сессию** с тестовым QRM-ключом перед следующей фазой.

**Review.**

---

### Phase 6 — Notifications (2 задачи)

```
→ coder-backend: 6a email+SMS   ‖ coder-tests: 6b
```

**Выход:** email + SMS уходят, reminder запланирован.

**Review.**

---

### Phase 7 — Admin UI (4 параллельные задачи)

```
→ coder-backend: 7a exports+billing+audit   ‖ coder-frontend: 7b organizer admin   ‖ coder-frontend: 7c platform admin   ‖ coder-tests: 7d
```

**Выход:** полноценные админки организатора и платформы.

**Review.**

---

### Phase 8 — Scanner (3 задачи)

```
→ coder-backend: 8a scanner API   ‖ coder-frontend: 8b PWA   ‖ coder-tests: 8c
```

**Выход:** рабочий сканер на мобильном.

**Review.**

---

### Phase 9 — Deploy (1 задача + полный review)

```
→ devops: phase-9 deploy
→ reviewer: full MVP audit
```

**Выход:** прод на `tdpay.ru`.

---

## Визуальная схема

```
Phase 0 (devops)
    │
    ▼
Phase 1 [BE skeleton ‖ FE skeleton ‖ BE models]  ──► review
    │
    ▼
Phase 2 [BE auth ‖ FE auth ‖ tests]  ──► review
    │
    ▼
Phase 3 [BE events ‖ FE admin-wiz ‖ FE vitrine ‖ tests]  ──► review
    │
    ▼
Phase 4 [BE booking ‖ FE booking ‖ tests]  ──► review
    │
    ▼
Phase 5 ┌─ BE QRM ─┐
        │          ▼
        │          ┌── BE tickets ──┐
        │          │                 │
        │          ├── FE pay/tkt ──► review
        │          │                 │
        │          └── tests ────────┘
    │
    ▼
Phase 6 [BE notifications ‖ tests]  ──► review
    │
    ▼
Phase 7 [BE admin-api ‖ FE org-admin ‖ FE platform ‖ tests]  ──► review
    │
    ▼
Phase 8 [BE scanner ‖ FE PWA ‖ tests]  ──► review
    │
    ▼
Phase 9 (devops + full review)  ──► LAUNCH 🚀
```

---

## Шаблон промпта для кодера

Когда архитектор запускает `coder-*`:

```
Контекст: ты — {backend|frontend|tests} кодер в проекте TD Pay (SaaS-платформа для продажи билетов с поддержкой QRM-оплаты).

Твоё ТЗ: прочитай {docs/specs/phase-NN-XX.md}.

Обязательный общий контекст (прочитай перед началом):
- AGENTS.md — соглашения проекта
- docs/ARCHITECTURE.md — общая архитектура (это источник истины)
- docs/DATA_MODEL.md — схема БД (если работаешь с БД)
- docs/API_CONTRACT.md — контракт API (если работаешь с API)

Текущее состояние репозитория: Phase {N-1} завершена. Соответствующий код есть в {backend/|frontend/}.

Задача: выполнить подпункт {Xa|Xb|Xc} из phase-spec.

Важно:
- Не делай больше, чем написано в spec
- Следуй существующим паттернам в коде
- Если есть сомнения — возвращайся с вопросом, не додумывай
- Не коммить, не пушь — архитектор сделает это сам
- Не трогай чужие файлы за пределами своей зоны ответственности

В финальном ответе верни:
1. Список созданных/изменённых файлов
2. Как проверить работу (команды)
3. Отклонения от spec, если были, с обоснованием
4. Что стоит учесть архитектору для следующей фазы
```

---

## Шаблон промпта для reviewer

```
Ты — code reviewer в проекте TD Pay.

Задача: провести код-ревью Phase {N}.

Что проверять:
1. Соответствие docs/specs/phase-{N}-*.md
2. Соответствие docs/ARCHITECTURE.md (приоритет над spec'ом при конфликтах)
3. Соблюдение AGENTS.md (стиль, именование, архитектура слоёв)
4. Безопасность:
   - Tenant isolation (organization_id везде)
   - Нет SQL-injection (только parametrized queries)
   - Секреты не в коде/логах
   - Webhook подпись проверяется
5. Типизация (mypy strict для BE, strict TS для FE)
6. Тесты: покрытие критичных путей, race conditions проверены
7. Миграции: reversible, idempotent
8. Нет TODO без тикета
9. Нет закомментированного кода

Приоритизация находок:
- 🔴 BLOCKER — надо чинить до мержа
- 🟡 WARNING — надо исправить, но не блокирует
- 🔵 NIT — вкусовое, по желанию

Верни структурированный отчёт по файлам с находками.
Не пиши код — только указывай на проблемы.
```

---

## Как архитектор работает после спринта

1. Получает результаты от всех параллельных подагентов.
2. Бегло проверяет главное (работает ли, соответствует ли spec).
3. Запускает `reviewer` на проверенные файлы.
4. Если `reviewer` нашёл BLOCKER — возвращает задачу кодеру через `task_id` с ссылкой на отчёт.
5. После чистого reviewer-отчёта → коммитит (только когда пользователь попросит!) → переходит к следующей фазе.

---

## Эскалация

Архитектор возвращается к пользователю (тебе) в случаях:
- Кодер не смог выполнить задачу из-за недостающей информации (редко)
- Возник архитектурный выбор, не описанный в ARCHITECTURE.md
- Нужны секреты / ключи / доступы (QRM API, SMS Aero, SSH к VPS)
- Важный риск обнаружен (например, QRM не отдаёт ожидаемый ответ)

В остальных случаях — выполняет самостоятельно.

---

## Готовность к запуску

Перед первым запуском `task` архитектор должен убедиться:
- [x] `docs/ARCHITECTURE.md` написан
- [x] `docs/DATA_MODEL.md` написан
- [x] `docs/API_CONTRACT.md` написан
- [x] `docs/ROADMAP.md` написан
- [x] Все `docs/specs/phase-*.md` написаны (0..9)
- [x] Пользователь заполнил REQUIREMENTS.md и REQUIREMENTS-2.md
- [ ] **Пользователь нажал кнопку «старт»** ← ждём
- [ ] Есть начальный доступ: репо git init (уже есть), .env.example (Phase 0 создаст)

Дальнейшие потребности в доступах:
- **Phase 5:** тестовый X-Api-Key QRM (уже есть: `7m9EkxnW.vJ9ROl7Bl7pjKxp1e1n9Gw9IyV6M46M1`)
- **Phase 6:** SMS Aero API key (тестовый можно без денег) + SMTP тест
- **Phase 9:** SSH ключ для Timeweb VPS, DNS API (Cloudflare recommended), прод-ключ QRM
