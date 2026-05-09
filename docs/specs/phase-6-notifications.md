# Phase 6 — Notifications (Email + SMS)

**Цель:** после оплаты гостю приходит email с PDF-билетом и SMS со ссылкой. За 6 часов до события — напоминание. При отмене — уведомление.

**Параллельные подзадачи:**
- 6a — Backend notifications (`coder-backend`)
- 6b — Tests (`coder-tests`)

**Зависит от:** Phase 5.
**Telegram-уведомления организаторам — откладываем на v1.0 (вместе с ботом).**

---

## 6a. Backend — `coder-backend`

### Integrations

#### Email (SMTP)

`integrations/email/smtp.py`:

- `aiosmtplib` клиент
- Поддержка двух режимов: TLS и plain (для mailhog в dev)
- Отправка с attachments (PDF)

**Шаблоны (jinja2):**

```
backend/src/paytools/templates/emails/
├── base.html                 # обёртка с брендом
├── ticket_issued.html        # выдача билета
├── ticket_refunded.html      # возврат
├── magic_link.html           # логин
└── organization_approved.html
```

- HTML + plain text версии (multipart/alternative)
- Inline-стили (многие клиенты режут `<style>`)
- Inline-изображения: логотип организатора + QR через CID
- PDF — вложением (attachment), name: `ticket-{event_slug}-{guest_last_name}.pdf`

#### SMS (SMS Aero)

`integrations/sms/smsaero.py`:

- HTTP-клиент (httpx)
- API docs: `https://smsaero.ru/api/` — basic auth (email + api_key)
- `send_sms(phone: str, text: str, sign: str) → str` (возвращает sms_id)

**Шаблоны SMS:** константы в `domain/notifications/sms_templates.py`.

Лимит 70 символов кириллицы на 1 SMS (или 160 латиница). Укорачиваем ссылки через `/t/{short_id}` redirect.

### Short-link redirect

`api/v1/public/short_link.py` (или отдельный `GET /t/{short_id}`):

- Храним в Redis: `shortlink:{id} → full_url`, TTL по событию
- При клике — 302 redirect

### Domain

`domain/notifications/service.py`:

- `NotificationService.send_ticket_email(reservation_id)`:
  - Подгружает reservation + tickets + event + organization
  - Рендерит шаблон `ticket_issued.html` с attachment первого билета (PDF). Если билетов > 1 — все PDF-ы в одном письме.
  - Отправляет через org.smtp_config или платформенный SMTP
  - Логирует попытку
  - Retry (arq retry 3x с экспоненциальным backoff)

- `NotificationService.send_ticket_sms(reservation_id)`:
  - Формирует текст с короткой ссылкой на билет
  - Отправляет через SMS Aero (если настроен и SMSAERO_API_KEY задан)
  - При ошибке — логирует, не ретраит (SMS — best effort)

- `NotificationService.send_reminder_sms(event_id)` (cron задача):
  - За 6 часов до `event.schedule.starts_at` (для single type; для sessions — по каждой сессии)
  - Все tickets со статусом `issued` для этого события
  - Отправляет напоминание

- `NotificationService.send_refund_notification(ticket_id)` — email + SMS

- `NotificationService.send_magic_link(email, token)` — email с ссылкой

### Arq tasks + scheduling

`workers/tasks/notifications.py`:

- `send_ticket_email_task(reservation_id)` — вызывается из issue_tickets
- `send_ticket_sms_task(reservation_id)`
- `send_refund_notifications(ticket_id)`

**Cron tasks (arq cron):**

- `schedule_event_reminders()` — каждые 15 минут сканирует events с `schedule.starts_at` в интервале now+5ч45мин..now+6ч15мин, ставит reminder-задачи

### Конфигурация per-organization

Если `organization.smtp_config` задан — используем его (sender from_name = organization.name), иначе платформенный SMTP с `from = "{organization.brand_name} <tickets@tdpay.ru>"`.

### Email blocklist updater

`workers/tasks/maintenance.py`:

- `update_email_blocklist()` — раз в неделю скачивает список disposable-доменов с github.com/disposable-email-domains/disposable-email-domains и обновляет таблицу

В MVP — захардкодить начальный список (~500 доменов), апдейтер — v1.0.

### Критерии готовности (6a)

- [ ] Email с PDF приходит в mailhog при оплате
- [ ] SMS отправляется (в dev — dry-run mode, в лог)
- [ ] Напоминание за 6 часов работает (тест: создать event через 6 часов, дождаться cron)
- [ ] Refund-уведомления работают
- [ ] Магик-линк работает
- [ ] Retry при ошибке SMTP
- [ ] Короткие ссылки работают

---

## 6b. Tests — `coder-tests`

### Unit

- Рендеринг шаблонов — snapshot tests (jinja output не меняется без причины)
- SMS template — длина ≤ 70 символов кириллицы после подстановки
- SMSAero client — mock httpx, проверка request body, парсинг response
- Short-link: генерация, проверка expiry

### Integration

- Отправка email через mailhog — проверяем что пришло: from, to, subject, attachments
- Отправка SMS — mock SMSAero API, проверяем параметры
- Cron-задача напоминаний: создаём event через 6ч, запускаем tick → видим reminder в очереди
- Config per-org: задан organization.smtp_config → используется он

### E2E

- Полный сценарий: бронь → оплата (через mock QRM) → email в mailhog с PDF → PDF валидный

---

## Что вернуть

Скриншоты писем (из mailhog) + примеры SMS текстов + логи cron
