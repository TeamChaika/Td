"""Эндпоинты для PWA-сканера."""

from fastapi import APIRouter

from paytools.api.v1.scanner.checkin import router as checkin_router

scanner_router = APIRouter()
scanner_router.include_router(checkin_router)
