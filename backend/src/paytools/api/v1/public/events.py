"""Публичные эндпоинты: витрина событий.

GET /public/events          — список опубликованных событий организации
GET /public/events/{slug}   — детали события + активные тарифы
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy.ext.asyncio import AsyncSession

from paytools.api.v1.deps import SessionDep, TenantOrganization
from paytools.api.v1.schemas.common import PaginatedResponse, Pagination
from paytools.api.v1.schemas.event import (
    PublicEventDetailResponse,
    PublicEventListItem,
    build_public_event_detail,
    build_public_event_list_item,
)
from paytools.core.errors import NotFoundError, OrganizationSuspendedError
from paytools.db.models.enums import OrganizationStatus
from paytools.db.models.organization import Organization
from paytools.db.repositories.event import EventRepository
from paytools.db.repositories.organization import OrganizationRepository
from paytools.domain.events.service import EventService

router = APIRouter()


def _build_event_service(session: AsyncSession) -> EventService:
    """Собрать EventService (без S3 — публичным эндпоинтам не нужен upload)."""
    event_repo = EventRepository(session)
    org_repo = OrganizationRepository(session)
    return EventService(
        session,
        event_repo=event_repo,
        org_repo=org_repo,
        s3_storage=None,
    )


def _require_active_org(org: Organization) -> None:
    """Проверить, что организация активна.

    Suspended → 403 (OrganizationSuspendedError).
    Pending_moderation → 404 (не раскрываем существование).
    """
    if org.status == OrganizationStatus.SUSPENDED:
        raise OrganizationSuspendedError()
    if org.status == OrganizationStatus.PENDING_MODERATION:
        raise NotFoundError("Организация не найдена", details={"slug": org.slug})


@router.get(
    "/events",
    response_model=PaginatedResponse[PublicEventListItem],
    summary="Список опубликованных событий",
    description=(
        "Возвращает только published события текущей организации. "
        "Сортировка по умолчанию: schedule.starts_at (ближайшие сверху)."
    ),
)
async def list_public_events(
    org: TenantOrganization,
    session: SessionDep,
    from_: Annotated[
        datetime | None, Query(alias="from", description="События с даты")
    ] = None,
    to: Annotated[datetime | None, Query(description="События до даты")] = None,
    sort: Annotated[
        str | None,
        Query(description="Сортировка: '-schedule' (по дате начала, убывание)"),
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedResponse[PublicEventListItem]:
    """Список опубликованных событий организации.

    Только active организации показывают события.
    Suspended/pending_moderation — 404.
    """
    _require_active_org(org)

    svc = _build_event_service(session)
    offset = (page - 1) * per_page

    events, total = await svc.list_public(
        org_id=org.id,
        from_date=from_,
        to_date=to,
        sort=sort,
        limit=per_page,
        offset=offset,
    )

    items = [build_public_event_list_item(e) for e in events]
    return PaginatedResponse[PublicEventListItem](
        items=items,
        pagination=Pagination.build(page=page, per_page=per_page, total=total),
    )


@router.get(
    "/events/{slug}",
    response_model=PublicEventDetailResponse,
    summary="Детали события по slug",
    description="Возвращает опубликованное событие с активными тарифами.",
)
async def get_public_event(
    slug: str,
    org: TenantOrganization,
    session: SessionDep,
) -> PublicEventDetailResponse:
    """Детали опубликованного события + активные тарифы.

    Только active организации показывают события.
    Suspended/pending_moderation — 404.
    """
    _require_active_org(org)

    svc = _build_event_service(session)
    event = await svc.get_by_slug_public(org.id, slug)

    # Фильтруем только активные тарифы
    tariffs = [
        t
        for t in (getattr(event, "tariffs", []) or [])
        if getattr(t, "is_active", False)
    ]

    return build_public_event_detail(event, tariffs)
