"""Публичные эндпоинты: валидация промокода.

POST /public/promocodes/validate — проверить промокод (без применения)
"""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from paytools.api.v1.deps import SessionDep, TenantOrganization
from paytools.api.v1.schemas.promocode import (
    PromoCodeValidateRequest,
    PromoCodeValidateResponse,
)
from paytools.db.repositories.event import EventRepository
from paytools.db.repositories.promocode import (
    PromoCodeRepository,
    PromoCodeUsageRepository,
)
from paytools.domain.promocodes.service import PromoService, ReservationItemInput

router = APIRouter()


def _build_promo_service(session: AsyncSession) -> PromoService:
    """Собрать PromoService."""
    return PromoService(
        session,
        promo_repo=PromoCodeRepository(session),
        usage_repo=PromoCodeUsageRepository(session),
    )


@router.post(
    "/promocodes/validate",
    response_model=PromoCodeValidateResponse,
    summary="Валидация промокода",
    description=(
        "Проверяет промокод без применения. Возвращает скидку "
        "или описание ошибки если промокод невалиден."
    ),
)
async def validate_promo_code(
    data: PromoCodeValidateRequest,
    org: TenantOrganization,
    session: SessionDep,
) -> PromoCodeValidateResponse:
    """Валидировать промокод.

    Tenant isolation: организация из subdomain.
    """
    svc = _build_promo_service(session)

    # Разрешаем цены тарифов для корректного расчёта скидки
    event_repo = EventRepository(session)
    event = await event_repo.get_with_tariffs(data.event_id)
    tariff_price_map = {t.id: t.price_kopecks for t in (event.tariffs if event else [])}

    result = await svc.validate(
        org_id=org.id,
        code=data.code,
        event_id=data.event_id,
        email=data.email,
        items=[
            ReservationItemInput(
                tariff_id=item.tariff_id,
                quantity=item.quantity,
                price_kopecks=tariff_price_map.get(item.tariff_id, 0),
            )
            for item in data.items
        ],
    )

    return PromoCodeValidateResponse(
        valid=result.valid,
        code=result.code,
        discount_type=result.discount_type,
        discount_value=result.discount_value,
        discount_kopecks=result.discount_kopecks,
        description=result.description,
        error_code=result.error_code,
        error_message=result.error_message,
    )
