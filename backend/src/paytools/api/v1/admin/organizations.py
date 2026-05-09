"""Эндпоинты админа: управление организациями.

GET   /admin/organizations              — список с пагинацией и фильтром
POST  /admin/organizations/{id}/approve — одобрить организацию
POST  /admin/organizations/{id}/suspend — заблокировать организацию
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy.ext.asyncio import AsyncSession

from paytools.api.v1.deps import SessionDep, SuperadminUser
from paytools.api.v1.schemas.common import OkResponse, PaginatedResponse, Pagination
from paytools.api.v1.schemas.organizations import (
    AdminOrganizationListItem,
    SuspendRequest,
)
from paytools.core.redis import get_redis_client
from paytools.db.models.enums import OrganizationStatus, UserRole
from paytools.db.repositories.audit import AuditLogRepository
from paytools.db.repositories.organization import OrganizationRepository
from paytools.db.repositories.user import UserRepository
from paytools.domain.audit.service import AuditService
from paytools.domain.organizations.service import OrganizationService

router = APIRouter()


def _build_org_service(session: AsyncSession) -> OrganizationService:
    """Собрать OrganizationService с нужными репозиториями и аудитом."""
    user_repo = UserRepository(session)
    org_repo = OrganizationRepository(session)
    audit_repo = AuditLogRepository(session, organization_id=None)
    audit_service = AuditService(session, repo=audit_repo)
    redis = get_redis_client()
    return OrganizationService(
        session,
        org_repo=org_repo,
        user_repo=user_repo,
        audit_service=audit_service,
        redis=redis,
    )


@router.get(
    "",
    response_model=PaginatedResponse[AdminOrganizationListItem],
    summary="Список организаций (админ)",
    description="Фильтрация по status. Пагинация через page/per_page.",
)
async def list_organizations(
    admin: SuperadminUser,
    session: SessionDep,
    status: Annotated[
        OrganizationStatus | None,
        Query(description="Фильтр по статусу"),
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedResponse[AdminOrganizationListItem]:
    """Список организаций с пагинацией и опциональным фильтром по статусу.

    Организации загружаются с eager-loading users через selectinload —
    один SQL-запрос вместо N+1.
    """
    org_repo = OrganizationRepository(session)
    offset = (page - 1) * per_page

    items = await org_repo.list_with_users(status=status, limit=per_page, offset=offset)
    total = (
        await org_repo.count_by_status(status)
        if status is not None
        else await org_repo.count()
    )

    # Берём email первого организатора из eager-загруженных users
    result_items: list[AdminOrganizationListItem] = []
    for org in items:
        owner = next((u for u in org.users if u.role == UserRole.ORGANIZER), None)
        item = AdminOrganizationListItem.model_validate(org)
        item.owner_email = owner.email if owner else None
        result_items.append(item)

    return PaginatedResponse[AdminOrganizationListItem](
        items=result_items,
        pagination=Pagination.build(page=page, per_page=per_page, total=total),
    )


@router.post(
    "/{org_id}/approve",
    response_model=OkResponse,
    summary="Одобрить организацию",
)
async def approve_organization(
    org_id: UUID,
    admin: SuperadminUser,
    session: SessionDep,
) -> OkResponse:
    """Одобрить организацию: перевести статус в ACTIVE.

    Только superadmin. Если организация уже ACTIVE — идемпотентно.
    """
    svc = _build_org_service(session)
    await svc.approve(org_id, by_user=admin)
    return OkResponse()


@router.post(
    "/{org_id}/suspend",
    response_model=OkResponse,
    summary="Заблокировать организацию",
)
async def suspend_organization(
    org_id: UUID,
    data: SuspendRequest,
    admin: SuperadminUser,
    session: SessionDep,
) -> OkResponse:
    """Заблокировать организацию: перевести статус в SUSPENDED.

    Только superadmin. reason обязателен (валидируется Pydantic-схемой).
    """
    svc = _build_org_service(session)
    await svc.suspend(org_id, by_user=admin, reason=data.reason)
    return OkResponse()
