"""Публичные эндпоинты (для гостей без авторизации).

Содержит роутеры для регистрации организаций, резолва tenant
по slug (брендинг для фронтового middleware), витрины событий,
бронирований и валидации промокодов.
"""

from fastapi import APIRouter

from paytools.api.v1.public.events import router as events_router
from paytools.api.v1.public.organizations import router as organizations_router
from paytools.api.v1.public.payments import router as payments_router
from paytools.api.v1.public.promocodes import router as promocodes_router
from paytools.api.v1.public.reservations import router as reservations_router
from paytools.api.v1.public.tenant import router as tenant_router

public_router = APIRouter()
public_router.include_router(organizations_router)
public_router.include_router(tenant_router)
public_router.include_router(events_router)
public_router.include_router(reservations_router)
public_router.include_router(promocodes_router)
public_router.include_router(payments_router)

