"""Smoke-тесты основных компонентов приложения."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_app_imports() -> None:
    """Приложение создаётся без исключений."""
    from paytools.main import app

    assert app is not None
    assert app.title == "TD Pay API"


def test_health_endpoint() -> None:
    """GET /health возвращает корректный JSON."""
    from paytools.main import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_has_routers() -> None:
    """В openapi.json присутствуют наши префиксы."""
    from paytools.main import app

    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json().get("paths", {})
    # Health обязателен
    assert "/health" in paths
    assert "/ready" in paths


def test_all_models_registered() -> None:
    """Все модели из DATA_MODEL.md зарегистрированы в metadata."""
    from paytools.db import models  # noqa: F401
    from paytools.db.base import Base

    expected = {
        "organizations",
        "users",
        "customers",
        "events",
        "tariffs",
        "reservations",
        "reservation_items",
        "tickets",
        "payments",
        "promo_codes",
        "promo_code_usages",
        "organization_balance",
        "balance_transactions",
        "deposits",
        "deposit_transactions",
        "webhook_deliveries",
        "audit_log",
        "email_blocklist",
    }
    actual = set(Base.metadata.tables.keys())
    missing = expected - actual
    assert not missing, f"Отсутствуют таблицы: {missing}"


def test_error_response_format() -> None:
    """Формат ошибок соответствует контракту `{"error": {"code", "message"}}`."""
    from paytools.main import app

    client = TestClient(app)
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert "error" in body
    assert "code" in body["error"]
    assert "message" in body["error"]
