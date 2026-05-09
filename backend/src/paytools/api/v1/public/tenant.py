"""GET /tenant/resolve — резолв организации по slug для фронтового middleware.

Используется фронтовым middleware для получения брендинга организации
(логотип, цветовая схема, название) до того, как пользователь авторизовался.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from paytools.api.v1.deps import SessionDep
from paytools.api.v1.schemas.organizations import PublicTenantResolveResponse
from paytools.core.errors import NotFoundError, OrganizationSuspendedError
from paytools.db.models.enums import OrganizationStatus
from paytools.db.repositories.organization import OrganizationRepository

router = APIRouter()


@router.get(
    "/tenant/resolve",
    response_model=PublicTenantResolveResponse,
    summary="Резолв организации по slug",
    description=(
        "Возвращает брендинг организации по slug (из query). "
        "Используется фронтовым middleware для рендера лендинга до логина."
    ),
    responses={
        200: {"description": "Организация найдена"},
        404: {"description": "Организация не найдена"},
        403: {"description": "Организация заблокирована"},
    },
)
async def resolve_tenant(
    slug: Annotated[str, Query(min_length=3, max_length=64)],
    session: SessionDep,
) -> PublicTenantResolveResponse:
    """Резолвить организацию по slug для предпросмотра брендинга.

    Slug не чувствителен к регистру: нормализуется (strip + lower)
    перед поиском. Не использует минимальную длину slug в 3 символа
    через query-валидацию — совпадает с доменным правилом SLUG_MIN_LENGTH.
    """
    org_repo = OrganizationRepository(session)
    org = await org_repo.get_by_slug(slug.strip().lower())

    if org is None:
        raise NotFoundError("Organization not found", details={"slug": slug})

    if org.status == OrganizationStatus.SUSPENDED:
        raise OrganizationSuspendedError("Organization suspended")

    return PublicTenantResolveResponse.model_validate(org)
