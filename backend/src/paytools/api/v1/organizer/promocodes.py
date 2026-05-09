"""Эндпоинты организатора: управление промокодами.

GET    /organizer/promocodes            — список промокодов
POST   /organizer/promocodes            — создать промокод
PATCH  /organizer/promocodes/{id}       — обновить промокод
DELETE /organizer/promocodes/{id}       — удалить/деактивировать промокод
GET    /organizer/promocodes/{id}/usages — история применений
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy.ext.asyncio import AsyncSession

from paytools.api.v1.deps import CurrentOrganization, OrganizerUser, SessionDep
from paytools.api.v1.schemas.common import OkResponse, PaginatedResponse, Pagination
from paytools.api.v1.schemas.promocode import (
    PromoCodeCreateRequest,
    PromoCodeResponse,
    PromoCodeUpdateRequest,
    PromoCodeUsageResponse,
    build_promo_code_response,
    build_promo_usage_response,
)
from paytools.db.repositories.promocode import (
    PromoCodeRepository,
    PromoCodeUsageRepository,
)
from paytools.domain.promocodes.service import (
    CreatePromoCodeInput,
    PromoService,
    UpdatePromoCodeInput,
)

router = APIRouter()


def _build_promo_service(session: AsyncSession) -> PromoService:
    """Собрать PromoService."""
    return PromoService(
        session,
        promo_repo=PromoCodeRepository(session),
        usage_repo=PromoCodeUsageRepository(session),
    )


@router.get(
    "",
    response_model=PaginatedResponse[PromoCodeResponse],
    summary="Список промокодов",
    description="Промокоды организации с фильтрами по event_id и is_active.",
)
async def list_promocodes(
    user: OrganizerUser,
    org: CurrentOrganization,
    session: SessionDep,
    event_id: Annotated[
        UUID | None, Query(description="Фильтр по событию")
    ] = None,
    is_active: Annotated[
        bool | None, Query(description="Фильтр по активности")
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedResponse[PromoCodeResponse]:
    """Список промокодов текущей организации."""
    repo = PromoCodeRepository(session, organization_id=org.id)

    items = await repo.list_for_organizer(
        org.id,
        event_id=event_id,
        is_active=is_active,
        limit=per_page,
        offset=(page - 1) * per_page,
    )
    total = await repo.count_for_organizer(
        org.id,
        event_id=event_id,
        is_active=is_active,
    )

    return PaginatedResponse[PromoCodeResponse](
        items=[build_promo_code_response(p) for p in items],
        pagination=Pagination.build(page=page, per_page=per_page, total=total),
    )


@router.post(
    "",
    response_model=PromoCodeResponse,
    status_code=201,
    summary="Создать промокод",
    description="Создаёт новый промокод для организации.",
)
async def create_promocode(
    data: PromoCodeCreateRequest,
    user: OrganizerUser,
    org: CurrentOrganization,
    session: SessionDep,
) -> PromoCodeResponse:
    """Создать промокод."""
    svc = _build_promo_service(session)

    promo = await svc.create(
        org_id=org.id,
        data=CreatePromoCodeInput(
            code=data.code,
            description=data.description,
            discount_type=data.discount_type,
            discount_value=data.discount_value,
            event_id=data.event_id,
            tariff_id=data.tariff_id,
            usage_limit=data.usage_limit,
            per_user_limit=data.per_user_limit,
            active_from=data.active_from,
            active_to=data.active_to,
            is_active=data.is_active,
            is_affiliate=data.is_affiliate,
            affiliate_user_id=data.affiliate_user_id,
        ),
    )

    return build_promo_code_response(promo)


@router.patch(
    "/{promo_id}",
    response_model=PromoCodeResponse,
    summary="Обновить промокод",
    description="PATCH-семантика: обновляются только переданные поля.",
)
async def update_promocode(
    promo_id: UUID,
    data: PromoCodeUpdateRequest,
    user: OrganizerUser,
    org: CurrentOrganization,
    session: SessionDep,
) -> PromoCodeResponse:
    """Обновить промокод."""
    svc = _build_promo_service(session)
    unset = data.model_dump(exclude_unset=True)

    promo = await svc.update(
        promo_id,
        data=UpdatePromoCodeInput(
            description=unset.get("description"),
            discount_type=unset.get("discount_type"),
            discount_value=unset.get("discount_value"),
            event_id=unset.get("event_id"),
            tariff_id=unset.get("tariff_id"),
            usage_limit=unset.get("usage_limit"),
            per_user_limit=unset.get("per_user_limit"),
            active_from=unset.get("active_from"),
            active_to=unset.get("active_to"),
            is_active=unset.get("is_active"),
        ),
    )

    return build_promo_code_response(promo)


@router.delete(
    "/{promo_id}",
    response_model=OkResponse,
    summary="Удалить промокод",
    description=(
        "Если есть использования — soft-delete (is_active=false). "
        "Если нет — полное удаление."
    ),
)
async def delete_promocode(
    promo_id: UUID,
    user: OrganizerUser,
    org: CurrentOrganization,
    session: SessionDep,
) -> OkResponse:
    """Удалить промокод."""
    svc = _build_promo_service(session)
    await svc.delete(promo_id)
    return OkResponse()


@router.get(
    "/{promo_id}/usages",
    response_model=PaginatedResponse[PromoCodeUsageResponse],
    summary="История применений промокода",
    description="Список всех использований конкретного промокода.",
)
async def list_promocode_usages(
    promo_id: UUID,
    user: OrganizerUser,
    org: CurrentOrganization,
    session: SessionDep,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 50,
) -> PaginatedResponse[PromoCodeUsageResponse]:
    """История применений промокода."""
    usage_repo = PromoCodeUsageRepository(session)

    items = await usage_repo.list_for_promo(
        promo_id,
        limit=per_page,
        offset=(page - 1) * per_page,
    )
    total = await usage_repo.count_for_promo(promo_id)

    return PaginatedResponse[PromoCodeUsageResponse](
        items=[build_promo_usage_response(u) for u in items],
        pagination=Pagination.build(page=page, per_page=per_page, total=total),
    )
