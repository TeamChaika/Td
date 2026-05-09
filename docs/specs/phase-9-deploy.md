# Phase 9 — Deploy & Launch

**Цель:** развернуть MVP на боевом сервере Timeweb Cloud, настроить домен `tdpay.ru` + wildcard, автодеплой из GitHub.

**Исполнитель:** `devops`, помогает `reviewer` на аудите.

---

## Что нужно сделать

### 1. Подготовка VPS Timeweb Cloud

Минимальные характеристики для MVP:
- **4 vCPU / 8 GB RAM / 80 GB SSD NVMe**
- Ubuntu 24.04 LTS
- Регион — Россия (Москва или СПб)
- Публичный IPv4 (статический)

Базовая настройка:
- Создать пользователя `deploy` с sudo и SSH-ключом
- Отключить root login
- UFW: open 22, 80, 443, 25 (если Postfix), 587
- fail2ban
- swap 4GB
- Docker + Docker Compose plugin
- Системный crontab для backup

### 2. DNS

В панели DNS (где управляется `tdpay.ru`):
- `A tdpay.ru → <VPS IP>`
- `A www.tdpay.ru → <VPS IP>`
- `A *.tdpay.ru → <VPS IP>` (wildcard для поддоменов организаторов)
- MX records — для Postfix (если отдельного домена нет, можно на этот же)
- TXT SPF: `v=spf1 ip4:<VPS IP> ~all`
- TXT DKIM — после настройки Postfix
- TXT DMARC: `v=DMARC1; p=none; rua=mailto:admin@tdpay.ru`

### 3. Nginx

`/etc/nginx/sites-available/tdpay`:

```nginx
# Landing (tdpay.ru)
server {
    listen 443 ssl http2;
    server_name tdpay.ru www.tdpay.ru;

    ssl_certificate /etc/letsencrypt/live/tdpay.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/tdpay.ru/privkey.pem;

    client_max_body_size 10m;

    # API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Short-link redirect
    location ~ ^/t/ {
        proxy_pass http://127.0.0.1:8000;
        ...
    }

    # Next.js
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}

# Wildcard для tenant-поддоменов
server {
    listen 443 ssl http2;
    server_name *.tdpay.ru;

    # Wildcard SSL
    ssl_certificate /etc/letsencrypt/live/tdpay.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/tdpay.ru/privkey.pem;

    # Тот же API и Next
    location /api/ { proxy_pass http://127.0.0.1:8000; ... }
    location / { proxy_pass http://127.0.0.1:3000; ... }
}

# HTTP → HTTPS redirect
server {
    listen 80;
    server_name tdpay.ru www.tdpay.ru *.tdpay.ru;
    return 301 https://$host$request_uri;
}
```

### 4. Let's Encrypt + wildcard

Для wildcard SSL нужен **DNS-01 challenge** (не HTTP-01). certbot с плагином провайдера DNS (если Timeweb не поддерживает — использовать acme.sh с Cloudflare/другой прокси, или ручное обновление через DNS API).

Если провайдер DNS не имеет плагина — варианты:
- Делегировать DNS на Cloudflare (бесплатно) → certbot-dns-cloudflare
- Или только основной домен + явные A-записи для каждого нового организатора (не масштабируется)

**Рекомендация:** Cloudflare DNS (CF только как DNS, не прокси) + `certbot-dns-cloudflare`.

```bash
certbot certonly \
  --dns-cloudflare \
  --dns-cloudflare-credentials ~/.secrets/cloudflare.ini \
  -d tdpay.ru -d '*.tdpay.ru' \
  --email admin@tdpay.ru
```

Cron: `0 3 * * * certbot renew --quiet && systemctl reload nginx`.

### 5. docker-compose.prod.yml

Отличия от dev:
- Нет MailHog / MinIO (используем внешний SMTP и S3 Timeweb)
- `postgres`, `redis`, `backend`, `worker`, `frontend` — все с `restart: always`
- Ресурсные лимиты (`mem_limit`, `cpus`)
- Логи через `logging: { driver: "json-file", options: { max-size: "100m", max-file: "5" } }`
- Volumes на диске: postgres data, redis data, pg_backups
- `.env.prod` читается

### 6. Postfix setup

На хост-машине (не в Docker):
- `postfix`, `opendkim`, `opendmarc`
- Конфиг relay-only (не принимаем почту, только отправляем)
- DKIM-ключ `tdpay`, публикуем в DNS
- SMTP_HOST=host.docker.internal:25 для backend-контейнера

Альтернатива: SMTP.bz / Unisender Go — если геморрой с настройкой. Но в требованиях — «Postfix на VPS», делаем его.

### 7. S3 (Timeweb Object Storage)

- Создать bucket `tdpay`
- CORS: разрешить загрузку с `tdpay.ru` и `*.tdpay.ru`
- Public read для фото событий (через CloudFront/Timeweb CDN если есть)
- Получить access_key / secret_key → в `.env.prod`

### 8. Backups

`/usr/local/bin/pg_backup.sh`:

```bash
#!/bin/bash
set -e
TS=$(date +%Y%m%d_%H%M%S)
docker compose exec -T postgres pg_dump -U tdpay tdpay | gzip > /tmp/tdpay_$TS.sql.gz
aws --endpoint=https://s3.timeweb.cloud s3 cp /tmp/tdpay_$TS.sql.gz s3://tdpay-backups/
rm /tmp/tdpay_$TS.sql.gz
# Retention: удаляем старше 30 дней
```

Cron: `0 4 * * * /usr/local/bin/pg_backup.sh >> /var/log/pg_backup.log 2>&1`.

### 9. GitHub Actions Deploy

`.github/workflows/deploy.yml`:

```yaml
name: Deploy to Production
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.DEPLOY_HOST }}
          username: deploy
          key: ${{ secrets.DEPLOY_SSH_KEY }}
          script: |
            cd /home/deploy/tdpay
            git pull origin main
            docker compose -f docker-compose.prod.yml pull
            docker compose -f docker-compose.prod.yml up -d --build
            docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

Secrets в GitHub:
- `DEPLOY_HOST`
- `DEPLOY_SSH_KEY`
- (опционально) `DOCKER_REGISTRY_TOKEN` если образы пушатся в registry

### 10. Первичное наполнение

- Создать суперадмина через manage-команду:
  ```bash
  docker compose exec backend python -m paytools.manage create-superadmin \
    --email admin@tdpay.ru --password ...
  ```
- Проверить health endpoint
- Зарегистрировать тестовую организацию → approve → создать тестовое событие → получить тестовый QR-платёж с тестовым ключом QRM → проверить весь flow
- **До публичного запуска** — дождаться прод-ключа QRM от организатора

### 11. Юридические страницы

Генерируем шаблоны:

- **`/terms`** — Публичная оферта
  - Указать: предмет, стоимость, условия возврата (общие + ссылка на organization.refund_policy), ответственность сторон, реквизиты TD Pay
- **`/privacy`** — Политика конфиденциальности по 152-ФЗ
  - Цели сбора, типы ПДн, срок хранения, права субъекта, контакты оператора
- **`/contacts`** — контакты платформы и организатора

Placement: `frontend/src/app/(landing)/terms/page.tsx` (общая оферта платформы) + на tenant-витрине отдельные страницы с подстановкой данных организации.

### 12. Runbook

`docs/RUNBOOK.md` (пишется параллельно):

- Как посмотреть логи
- Как перезапустить сервис
- Как восстановить БД из бэкапа
- Как подключить нового организатора (manual approve через API)
- Как обновить wildcard SSL если certbot сломался
- Контакты поддержки QRM, SMS Aero, Timeweb

### 13. Review сессия

**Reviewer:**
- Проверить `ARCHITECTURE.md` vs реализация
- Security audit:
  - Все webhook проверяют подпись
  - Нет утечек секретов в логах
  - Rate limit backdoor (даже если выключен) тест
  - SQL injection — везде Parametrized через SQLAlchemy
  - XSS в пользовательских полях — на фронте `react-markdown` правильно настроен
  - CORS правильно настроен
  - JWT — короткий TTL, refresh rotation
- Проверить tenant isolation тестами
- Проверить что все модели имеют индексы на часто-запрашиваемых полях
- Проверить миграции (idempotent, reversible)

---

## Критерии готовности

- [ ] https://tdpay.ru — открывается лендинг
- [ ] https://acme.tdpay.ru (тестовая организация) — открывается витрина
- [ ] https://tdpay.ru/admin — работает логин
- [ ] https://tdpay.ru/platform — работает superadmin
- [ ] Wildcard SSL валидный
- [ ] Email отправляется, DKIM/SPF валидны (проверка через mail-tester.com)
- [ ] SMS отправляется (тест с реальным номером)
- [ ] Тестовая покупка через тестовый QRM-ключ проходит полностью
- [ ] Бэкап работает, тестовое восстановление успешно
- [ ] GitHub Actions деплой проходит автоматически
- [ ] Все critical-логи в `/var/log/docker/` доступны
- [ ] Runbook написан

---

## Что вернуть

Checklist с отмеченными пунктами + ссылка на работающий прод + скрины тестовой покупки
