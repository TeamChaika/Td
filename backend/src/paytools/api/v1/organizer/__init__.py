"""Эндпоинты для организаторов."""

from fastapi import APIRouter

from paytools.api.v1.organizer.events import router as events_router
from paytools.api.v1.organizer.organization import router as organization_router
from paytools.api.v1.organizer.payments import router as payments_router
from paytools.api.v1.organizer.promocodes import router as promocodes_router
from paytools.api.v1.organizer.reservations import router as reservations_router
from paytools.api.v1.organizer.tariffs import router as tariffs_router

organizer_router = APIRouter()
organizer_router.include_router(organization_router, prefix="/organization")
organizer_router.include_router(events_router, prefix="/events")
organizer_router.include_router(tariffs_router, prefix="")
organizer_router.include_router(reservations_router, prefix="/reservations")
organizer_router.include_router(promocodes_router, prefix="/promocodes")
organizer_router.include_router(payments_router, prefix="")

