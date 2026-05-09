"""Integration-тесты SMS-отправки через SMS Aero (с моками HTTP)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from paytools.integrations.sms import (
    SMSError,
    build_reminder_sms,
    build_ticket_sms,
    send_sms,
)


class TestSMSSending:
    """Тесты отправки SMS с замоканным HTTP."""

    async def test_send_sms_success(self, monkeypatch) -> None:
        """Успешная отправка SMS: не падает при success=true."""
        monkeypatch.setattr(
            "paytools.integrations.sms.get_settings",
            lambda: _fake_settings(smsaero_email="a@b.com", smsaero_api_key="key123"),
        )

        mock_resp = AsyncMock()
        mock_resp.raise_for_status = lambda: None
        mock_resp.json = lambda: {"success": True}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Не должно упасть
            await send_sms(phone="79001234567", text="Test SMS from test")

        # Проверяем что post был вызван с правильными параметрами
        call_args = mock_client.post.call_args
        assert call_args is not None
        url = call_args[0][0]
        assert "smsaero.ru" in url
        json_body = call_args[1]["json"]
        assert json_body["number"] == "79001234567"
        assert "Test SMS" in json_body["text"]
        assert json_body["sign"] == "TDPay"

    async def test_send_sms_dev_mode_noop(self, monkeypatch) -> None:
        """В dev-режиме (без API-ключа) — не отправляет, не падает."""
        monkeypatch.setattr(
            "paytools.integrations.sms.get_settings",
            lambda: _fake_settings(smsaero_email="", smsaero_api_key=""),
        )

        # Не должно упасть
        await send_sms(phone="79001234567", text="Test SMS")

    async def test_send_sms_api_error(self, monkeypatch) -> None:
        """SMS Aero вернул success=false → SMSError."""
        monkeypatch.setattr(
            "paytools.integrations.sms.get_settings",
            lambda: _fake_settings(smsaero_email="a@b.com", smsaero_api_key="key123"),
        )

        mock_resp = AsyncMock()
        mock_resp.raise_for_status = lambda: None
        mock_resp.json = lambda: {"success": False, "message": "Invalid number"}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(SMSError, match="Invalid number"):
                await send_sms(phone="bad", text="Test")

    async def test_send_sms_http_error(self, monkeypatch) -> None:
        """HTTP-ошибка от SMS Aero → SMSError."""
        monkeypatch.setattr(
            "paytools.integrations.sms.get_settings",
            lambda: _fake_settings(smsaero_email="a@b.com", smsaero_api_key="key123"),
        )

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Server error",
                request=AsyncMock(),
                response=AsyncMock(status_code=500),
            )
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(SMSError, match="Failed to send SMS"):
                await send_sms(phone="79001234567", text="Test")


class TestSMSTemplates:
    """Тесты SMS-шаблонов (чистые функции)."""

    def test_ticket_sms_format(self) -> None:
        text = build_ticket_sms(
            event_title="Концерт",
            event_date="01.01.2027 20:00",
            ticket_count=3,
            first_code="ABCD-EFGH",
        )
        assert "TD Pay" in text
        assert "Концерт" in text
        assert "3" in text
        assert "ABCD-EFGH" in text

    def test_reminder_sms_format(self) -> None:
        text = build_reminder_sms(
            event_title="Фестиваль",
            event_date="01.06.2027",
            event_time="18:00",
        )
        assert "TD Pay" in text
        assert "Фестиваль" in text
        assert "18:00" in text
        assert "Напоминание" in text


def _fake_settings(**kwargs):
    """Создать фейковые настройки для тестов."""
    from paytools.core.config import Settings

    return Settings(
        env="test",
        database_url="postgresql+asyncpg://localhost/db",
        redis_url="redis://localhost/0",
        secret_key="a" * 32,
        fernet_key="DoS7l0dqk2ewkyuqDsLLWpTi1i2FWzA_AZAjjuHQXKg=",
        jwt_secret="b" * 32,
        s3_endpoint="http://localhost:9000",
        s3_access_key="minio",
        s3_secret_key="minio123",
        smtp_host="localhost",
        smtp_port=1025,
        smtp_from="test@tdpay.local",
        smsaero_email=kwargs.get("smsaero_email", ""),
        smsaero_api_key=kwargs.get("smsaero_api_key", ""),
        smsaero_sign="TDPay",
    )
