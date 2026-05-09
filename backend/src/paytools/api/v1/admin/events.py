"""Эндпоинты админа: модерация событий.

GET  /admin/events?status=pending_moderation  — очередь модерации
POST /admin/events/{id}/publish               — опубликовать (модерация)
POST /admin/events/{id}/reject                — отклонить
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy.ext.asyncio import AsyncSession

from paytools.api.v1.deps import SessionDep, SuperadminUser
from paytools.api.v1.schemas.common import OkResponse, PaginatedResponse, Pagination
from paytools.api.v1.schemas.event import (
    AdminEventListItem,
    EventDetailResponse,
    RejectEventRequest,
    build_event_detail,
)
from paytools.db.repositories.event import EventRepository
from paytools.db.repositories.organization import OrganizationRepository
from paytools.domain.events.service import EventService

router = APIRouter()


def _build_event_service(session: AsyncSession) -> EventService:
    """Собрать EventService для админа."""
    event_repo = EventRepository(session)
    org_repo = OrganizationRepository(session)
    return EventService(
        session,
        event_repo=event_repo,
        org_repo=org_repo,
        s3_storage=None,
    )


@router.get(
    "",
    response_model=PaginatedResponse[AdminEventListItem],
    summary="Очередь модерации событий",
    description="Список событий со всех организаций в статусе pending_moderation.",
)
async def list_pending_events(
    admin: SuperadminUser,
    session: SessionDep,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedResponse[AdminEventListItem]:
    """Список событий на модерации."""
    svc = _build_event_service(session)
    offset = (page - 1) * per_page

    events, total = await svc.list_pending_moderation(
        limit=per_page,
        offset=offset,
    )

    items = [AdminEventListItem.model_validate(e) for e in events]
    return PaginatedResponse[AdminEventListItem](
        items=items,
        pagination=Pagination.build(page=page, per_page=per_page, total=total),
    )


@router.post(
    "/{event_id}/publish",
    response_model=EventDetailResponse,
    summary="Опубликовать событие (модерация)",
    description="Superadmin публикует событие из pending_moderation.",
)
async def admin_publish_event(
    event_id: UUID,
    admin: SuperadminUser,
    session: SessionDep,
) -> EventDetailResponse:
    """Опубликовать событие (модерация суперадмином)."""
    svc = _build_event_service(session)
    event = await svc.publish(event_id, by_user=admin)
    tariffs = getattr(event, "tariffs", []) or []
    return build_event_detail(event, tariffs)


@router.post(
    "/{event_id}/reject",
    response_model=OkResponse,
    summary="Отклонить событие (модерация)",
    description="Superadmin отклоняет событие с указанием причины.",
)
async def admin_reject_event(
    event_id: UUID,
    data: RejectEventRequest,
    admin: SuperadminUser,
    session: SessionDep,
) -> OkResponse:
    """Отклонить событие (модерация)."""
    svc = _build_event_service(session)
    await svc.reject(event_id, note=data.note, by_user=admin)
    return OkResponse()
