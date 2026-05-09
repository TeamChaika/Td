# TD Pay — команды локальной разработки.
# Требуется: Docker + Docker Compose plugin. pnpm/uv не нужны на хосте — всё в контейнерах.

.PHONY: help up down restart logs ps \
        migrate migration \
        be-shell fe-shell \
        be-test fe-test test \
        be-lint fe-lint lint \
        be-typecheck fe-typecheck typecheck \
        be-format fe-format format \
        clean

# По умолчанию — help
.DEFAULT_GOAL := help

help: ## Показать этот список команд
	@awk 'BEGIN {FS = ":.*##"; printf "Доступные команды:\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

# ---- Docker Compose ----

up: ## Поднять все сервисы в фоне
	docker compose up -d --build

down: ## Остановить все сервисы
	docker compose down

restart: ## Перезапустить сервисы
	docker compose restart

logs: ## Показать логи (или конкретного сервиса: make logs svc=backend)
	@if [ -z "$(svc)" ]; then docker compose logs -f --tail=100; \
	else docker compose logs -f --tail=100 $(svc); fi

ps: ## Статус контейнеров
	docker compose ps

# ---- Alembic ----

migrate: ## Применить миграции (alembic upgrade head)
	docker compose exec backend alembic upgrade head

migration: ## Создать новую миграцию: make migration name=add_users
	@if [ -z "$(name)" ]; then echo "Usage: make migration name=<snake_case_name>"; exit 1; fi
	docker compose exec backend alembic revision --autogenerate -m "$(name)"

# ---- Shells ----

be-shell: ## Войти в shell backend-контейнера
	docker compose exec backend sh

fe-shell: ## Войти в shell frontend-контейнера
	docker compose exec frontend sh

# ---- Тесты ----

be-test: ## Тесты бэкенда
	docker compose exec backend pytest -q

fe-test: ## Тесты фронтенда
	docker compose exec frontend pnpm test -- --run

test: be-test fe-test ## Все тесты

# ---- Линт ----

be-lint: ## Ruff check на бэкенде
	docker compose exec backend ruff check .

fe-lint: ## ESLint на фронтенде
	docker compose exec frontend pnpm lint

lint: be-lint fe-lint ## Линт всего

# ---- Type-check ----

be-typecheck: ## mypy на бэкенде
	docker compose exec backend mypy src

fe-typecheck: ## tsc --noEmit на фронтенде
	docker compose exec frontend pnpm type-check

typecheck: be-typecheck fe-typecheck ## Type-check всего

# ---- Форматирование ----

be-format: ## Отформатировать бэкенд (ruff format)
	docker compose exec backend ruff format .

fe-format: ## Отформатировать фронтенд (prettier)
	docker compose exec frontend pnpm exec prettier --write "src/**/*.{ts,tsx,css}"

format: be-format fe-format ## Отформатировать всё

# ---- Очистка ----

clean: ## Снести контейнеры и volumes (ВСЕ ДАННЫЕ ПРОПАДУТ!)
	docker compose down -v
