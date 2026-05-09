"""Auth-роутер — экспортируется для подключения в ``api/v1/router.py``."""

from fastapi import APIRouter

from paytools.api.v1.auth.routes import router

auth_router = APIRouter()
auth_router.include_router(router)
