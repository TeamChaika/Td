"""Главный роутер API v1 — собирает все sub-routers."""

from __future__ import annotations

from fastapi import APIRouter

from paytools.api.v1.admin import admin_router
from paytools.api.v1.auth import auth_router
from paytools.api.v1.organizer import organizer_router
from paytools.api.v1.public import public_router
from paytools.api.v1.scanner import scanner_router
from paytools.api.v1.webhooks import webhooks_router

v1_router = APIRouter()

# Наполнение sub-роутеров — в последующих фазах.
v1_router.include_router(public_router, prefix="/public", tags=["public"])
v1_router.include_router(auth_router, prefix="/auth", tags=["auth"])
v1_router.include_router(organizer_router, prefix="/organizer", tags=["organizer"])
v1_router.include_router(scanner_router, prefix="/scanner", tags=["scanner"])
v1_router.include_router(admin_router, prefix="/admin", tags=["admin"])
v1_router.include_router(webhooks_router, prefix="/webhooks", tags=["webhooks"])
