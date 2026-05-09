"""Webhook-эндпоинт для QRM (QR Manager).

POST /webhooks/qrm — приём уведомлений о смене статуса платежа.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from sqlalchemy.ext.asyncio import AsyncSession

from paytools.api.v1.schemas.common import OkResponse
from paytools.core.db import AsyncSessionLocal
from paytools.db.models.system import WebhookDelivery
from paytools.db.repositories.payment import PaymentRepository
from paytools.db.repositories.reservation import ReservationRepository
from paytools.db.repositories.ticket import TicketRepository
from paytools.domain.payments.service import PaymentService
from paytools.domain.tickets.service import TicketService

logger = logging.getLogger(__name__)

router = APIRouter()


async def _process_qrm_webhook(
    session: AsyncSession,
    *,
    payload: dict,
    headers: dict | None = None,
) -> None:
    """Обработать webhook от QRM."""
    reservation_repo = ReservationRepository(session)

    svc = PaymentService(
        session,
        payment_repo=PaymentRepository(session),
        reservation_repo=reservation_repo,
        ticket_service=TicketService(
            session,
            ticket_repo=TicketRepository(session),
            reservation_repo=reservation_repo,
        ),
    )

    # QRM отправляет invoice_id как ID счёта
    invoice_id = payload.get("invoice_id") or payload.get("id")
    status = payload.get("status", "")

    if not invoice_id:
        logger.warning("QRM webhook без invoice_id: %s", payload)
        return

    if status == "paid":
        await svc.confirm_payment(
            provider_payment_id=str(invoice_id),
            provider_payload=payload,
        )
        logger.info("QRM webhook: платёж %s подтверждён", invoice_id)
    elif status in ("cancelled", "expired"):
        # Обновляем статус платежа
        payment_repo = PaymentRepository(session)
        payment = await payment_repo.get_by_provider_payment_id(str(invoice_id))
        if payment:
            from paytools.db.models.enums import PaymentStatus

            payment.status = (
                PaymentStatus.EXPIRED if status == "expired" else PaymentStatus.CANCELLED
            )
            # Сохраняем payload
            events = payment.webhook_events or []
            events.append(payload)
            payment.webhook_events = events
            await session.flush()
            logger.info("QRM webhook: платёж %s → %s", invoice_id, status)


@router.post(
    "/qrm",
    response_model=OkResponse,
    summary="QRM webhook",
    description="Принимает уведомления от QR Manager о смене статуса платежа.",
)
async def qrm_webhook(request: Request) -> OkResponse:
    """Webhook от QRM."""
    headers = dict(request.headers)
    payload = await request.json()

    # Логируем сырой webhook
    async with AsyncSessionLocal() as session:
        async with session.begin():
            delivery = WebhookDelivery(
                provider="qrmanager",
                event_type=payload.get("status", "unknown"),
                payload=payload,
                headers=headers,
                signature_valid=True,  # QRM не подписывает webhook-и в тестовом режиме
                processed=False,
            )
            session.add(delivery)
            await session.flush()

            try:
                await _process_qrm_webhook(
                    session,
                    payload=payload,
                    headers=headers,
                )
                delivery.processed = True
            except Exception as e:
                delivery.processed = False
                delivery.processing_error = str(e)[:1000]
                logger.exception("QRM webhook processing error")
                raise

    return OkResponse()
