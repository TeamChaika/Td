"""Webhook-эндпоинты (QRM). Наполняется в Phase 5+."""

from fastapi import APIRouter

from paytools.api.v1.webhooks.qrm import router as qrm_router

webhooks_router = APIRouter()
webhooks_router.include_router(qrm_router)
