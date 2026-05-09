"""Integration-тесты настроек организатора."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestOrganizerSettings:
    """Тесты GET/PATCH /api/v1/organizer/organization."""

    @pytest.fixture(autouse=True)
    async def _setup(self, organizer_user) -> None:
        """Гарантируем что тестовый пользователь создан."""
        pass

    async def _get_organizer_token(self, client: AsyncClient) -> str:
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "organizer@test-org.example.com",
                "password": "Organizer123!",
            },
        )
        assert resp.status_code == 200
        return resp.json()["access_token"]

    async def test_get_my_organization_returns_200(self, client: AsyncClient) -> None:
        """GET /organizer/organization возвращает настройки."""
        token = await self._get_organizer_token(client)

        resp = await client.get(
            "/api/v1/organizer/organization",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["slug"] == "test-org"
        assert body["status"] == "active"
        assert "qrm_api_key_masked" in body

    async def test_patch_updates_settings(self, client: AsyncClient) -> None:
        """PATCH /organizer/organization обновляет настройки."""
        token = await self._get_organizer_token(client)

        resp = await client.patch(
            "/api/v1/organizer/organization",
            json={
                "brand_name": "My Brand",
                "brand_color": "#FF5500",
                "contact_email": "info@mybrand.ru",
                "legal_inn": "1234567890",
                "telegram_chat_id": 123456789,
                "qrm_api_login": "my_qrm_login",
                "refund_policy": "Возврат в течение 7 дней",
                "timezone": "Asia/Yekaterinburg",
                "legal_entity_type": "ooo",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["brand_name"] == "My Brand"
        assert body["brand_color"] == "#FF5500"
        assert body["contact_email"] == "info@mybrand.ru"
        assert body["legal_inn"] == "1234567890"
        assert body["telegram_chat_id"] == 123456789
        assert body["qrm_api_login"] == "my_qrm_login"
        assert body["refund_policy"] == "Возврат в течение 7 дней"
        assert body["timezone"] == "Asia/Yekaterinburg"
        assert body["legal_entity_type"] == "ooo"

        # GET должен вернуть те же обновлённые значения
        get_resp = await client.get(
            "/api/v1/organizer/organization",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert get_resp.status_code == 200
        get_body = get_resp.json()
        assert get_body["brand_name"] == "My Brand"
        assert get_body["contact_email"] == "info@mybrand.ru"
        assert get_body["legal_inn"] == "1234567890"
        assert get_body["telegram_chat_id"] == 123456789
        assert get_body["qrm_api_login"] == "my_qrm_login"
        assert get_body["refund_policy"] == "Возврат в течение 7 дней"
        assert get_body["timezone"] == "Asia/Yekaterinburg"
        assert get_body["legal_entity_type"] == "ooo"

    async def test_qrm_api_key_is_masked_in_response(self, client: AsyncClient) -> None:
        """QRM-ключ в ответе маскирован (не plaintext)."""
        token = await self._get_organizer_token(client)

        resp = await client.patch(
            "/api/v1/organizer/organization",
            json={"qrm_api_key": "sk_live_test_key_12345678"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()

        masked = body.get("qrm_api_key_masked")
        assert masked is not None
        assert masked.startswith("****")
        assert masked.endswith("5678")

        assert "qrm_api_key_encrypted" not in body
        assert "sk_live_test_key_12345678" not in str(body)

    async def test_organizer_sees_own_organization_in_get(
        self, client: AsyncClient
    ) -> None:
        """Организатор видит данные своей организации через GET."""
        token = await self._get_organizer_token(client)

        resp = await client.get(
            "/api/v1/organizer/organization",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["slug"] == "test-org"
