"""QRM (QR Manager) — платёжный провайдер для приёма оплаты по QR-коду.

API QRM (документация: https://docs.qrm.ooo):
  POST /api/v1/invoice/create  — создать счёт
  GET  /api/v1/invoice/status  — статус счёта
  GET  /api/v1/invoice/qr      — QR-код (PNG base64)

Два режима:
  - Тестовый (qrm_base_url + qrm_test_api_key)
  - Боевой (api_key организации + логин)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from httpx import HTTPStatusError, RequestError


@dataclass(slots=True, kw_only=True)
class QRMInvoice:
    """Результат создания счёта в QRM."""

    invoice_id: str
    qr_url: str
    qr_image_base64: str | None = None
    payment_url: str | None = None


@dataclass(slots=True, kw_only=True)
class QRMStatus:
    """Статус счёта в QRM."""

    invoice_id: str
    status: str  # pending | paid | expired | cancelled | refunded
    amount_kopecks: int


class QRMError(Exception):
    """Ошибка при взаимодействии с QRM API."""


class QRMClient:
    """Клиент к QR Manager API.

    Использование:
        client = QRMClient(base_url="https://app.devwapiserv.qrm.ooo")
        invoice = await client.create_invoice(
            amount_kopecks=100000,
            description="Билет на концерт",
            invoice_id="reservation-uuid",
            callback_url="https://example.com/webhooks/qrm",
            api_key="test-key",
            login="test-login",
        )
        status = await client.get_status(invoice.invoice_id, api_key="test-key")
    """

    def __init__(
        self,
        base_url: str = "https://app.devwapiserv.qrm.ooo",
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def create_invoice(
        self,
        *,
        amount_kopecks: int,
        description: str,
        invoice_id: str,
        callback_url: str,
        api_key: str,
        login: str,
        email: str | None = None,
        phone: str | None = None,
    ) -> QRMInvoice:
        """Создать счёт (QR-код) в QRM.

        amount_kopecks — сумма в копейках (QRM ожидает рубли, конвертируем).
        invoice_id — наш внутренний ID (payment.id).
        """
        url = f"{self.base_url}/api/v1/invoice/create"
        body: dict[str, Any] = {
            "amount": amount_kopecks / 100,  # QRM работает в рублях
            "description": description,
            "externalId": invoice_id,
            "callbackUrl": callback_url,
        }
        if email:
            body["customerEmail"] = email
        if phone:
            body["customerPhone"] = phone

        data = await self._request("POST", url, json=body, api_key=api_key, login=login)
        return QRMInvoice(
            invoice_id=data["id"],
            qr_url=data.get("qrUrl", ""),
            qr_image_base64=data.get("qrImage"),
            payment_url=data.get("paymentUrl"),
        )

    async def get_status(
        self,
        invoice_id: str,
        *,
        api_key: str,
        login: str,
    ) -> QRMStatus:
        """Получить статус счёта из QRM."""
        url = f"{self.base_url}/api/v1/invoice/status"
        data = await self._request(
            "GET", url, params={"id": invoice_id}, api_key=api_key, login=login
        )
        return QRMStatus(
            invoice_id=data["id"],
            status=data.get("status", "pending"),
            amount_kopecks=int(float(data.get("amount", 0)) * 100),
        )

    async def _request(
        self,
        method: str,
        url: str,
        *,
        api_key: str,
        login: str,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Выполнить HTTP-запрос к QRM API с обработкой ошибок."""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "X-Login": login,
            "Accept": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.request(
                    method, url, json=json, params=params, headers=headers
                )
                resp.raise_for_status()
                return resp.json()  # type: ignore[no-any-return]
        except HTTPStatusError as e:
            body = e.response.text
            raise QRMError(
                f"QRM API error {e.response.status_code}: {body[:500]}"
            ) from e
        except RequestError as e:
            raise QRMError(f"QRM API request failed: {e}") from e
