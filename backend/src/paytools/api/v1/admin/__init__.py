"""Эндпоинты для суперадмина платформы."""

from fastapi import APIRouter

from paytools.api.v1.admin.events import router as events_router
from paytools.api.v1.admin.organizations import router as organizations_router

admin_router = APIRouter()
admin_router.include_router(organizations_router, prefix="/organizations")
admin_router.include_router(events_router, prefix="/events")
