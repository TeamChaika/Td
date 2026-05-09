"""Эндпоинты организатора: управление событиями.

POST   /organizer/events           — создать событие (draft)
GET    /organizer/events           — список своих событий
GET    /organizer/events/{id}      — детали события
PATCH  /organizer/events/{id}      — обновить событие
DELETE /organizer/events/{id}      — архивировать событие
POST   /organizer/events/{id}/submit  — отправить на модерацию
POST   /organizer/events/{id}/publish — опубликовать (если auto_publish)
POST   /organizer/events/{id}/images  — загрузить изображение
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from paytools.api.v1.deps import CurrentOrganization, OrganizerUser, SessionDep
from paytools.api.v1.schemas.common import OkResponse, PaginatedResponse, Pagination
from paytools.api.v1.schemas.event import (
    EventCreateRequest,
    EventCreateResponse,
    EventDetailResponse,
    EventListItem,
    EventUpdateRequest,
    build_event_detail,
    build_event_list_item,
)
from paytools.core.config import get_settings
from paytools.core.errors import NotFoundError
from paytools.db.models.enums import EventStatus
from paytools.db.repositories.event import EventRepository
from paytools.db.repositories.organization import OrganizationRepository
from paytools.domain.events.service import (
    CreateEventInput,
    EventService,
    UpdateEventInput,
)
from paytools.integrations.storage.s3 import S3Config, S3Storage

router = APIRouter()


def _build_event_service(session: AsyncSession) -> EventService:
    """Собрать EventService с репозиториями и S3."""
    settings = get_settings()
    event_repo = EventRepository(session)
    org_repo = OrganizationRepository(session)
    s3_config = S3Config(
        endpoint_url=settings.s3_endpoint,
        bucket=settings.s3_bucket,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        region=settings.s3_region,
        public_endpoint=settings.s3_public_endpoint,
    )
    s3_storage = S3Storage(s3_config)
    return EventService(
        session,
        event_repo=event_repo,
        org_repo=org_repo,
        s3_storage=s3_storage,
    )


def _safe_serialize_pydantic(value: object) -> dict[str, object]:
    """Безопасно сериализовать Pydantic-модель или сырой dict в dict."""
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")  # type: ignore[no-any-return]
    if isinstance(value, dict):
        return cast(dict[str, object], value)
    return {}


def _safe_serialize_fields(value: object) -> list[dict[str, object]] | None:
    """Безопасно сериализовать список Pydantic custom fields."""
    if value is None:
        return None
    if isinstance(value, list):
        result: list[dict[str, object]] = []
        for f in value:
            if hasattr(f, "model_dump"):
                result.append(f.model_dump(mode="json"))
            else:
                result.append(cast(dict[str, object], f))
        return result
    return None


async def _require_event_for_org(
    session: AsyncSession, event_id: UUID, org_id: UUID
) -> EventDetailResponse:
    """Загрузить событие с проверкой org-принадлежности.

    Возвращает событие с eager-loaded тарифами.
    Если событие не найдено или принадлежит другой org — 404.
    """
    event_repo = EventRepository(session)
    event = await event_repo.get_with_tariffs_for_org(event_id, org_id)
    if event is None:
        raise NotFoundError("Событие не найдено", details={"event_id": str(event_id)})
    tariffs = getattr(event, "tariffs", []) or []
    return build_event_detail(event, tariffs)


# --------------------------------------------------------------------------- #
# CRUD
# --------------------------------------------------------------------------- #


@router.post(
    "",
    response_model=EventCreateResponse,
    status_code=201,
    summary="Создать событие",
    description="Создаёт событие в статусе draft.",
)
async def create_event(
    data: EventCreateRequest,
    user: OrganizerUser,
    org: CurrentOrganization,
    session: SessionDep,
) -> EventDetailResponse:
    """Создать новое событие в статусе draft."""
    svc = _build_event_service(session)

    event = await svc.create(
        org_id=org.id,
        data=CreateEventInput(
            title=data.title,
            slug=data.slug,
            description_md=data.description_md,
            location_name=data.location_name,
            location_address=data.location_address,
            location_lat=data.location_lat,
            location_lng=data.location_lng,
            schedule=data.schedule.model_dump(mode="json"),
            capacity_policy=data.capacity_policy.model_dump(mode="json"),
            custom_fields_schema=(
                [f.model_dump(mode="json") for f in data.custom_fields_schema]
                if data.custom_fields_schema
                else None
            ),
        ),
    )

    # Для нового события тарифов ещё нет — не дёргаем lazy-load
    tariffs: list[object] = []
    return build_event_detail(event, tariffs)


@router.get(
    "",
    response_model=PaginatedResponse[EventListItem],
    summary="Список событий организатора",
    description="Фильтры: status, search, from/to по дате. Пагинация.",
)
async def list_my_events(
    user: OrganizerUser,
    org: CurrentOrganization,
    session: SessionDep,
    status: Annotated[
        EventStatus | None, Query(description="Фильтр по статусу")
    ] = None,
    search: Annotated[
        str | None, Query(description="Поиск по названию/локации")
    ] = None,
    from_: Annotated[
        datetime | None, Query(alias="from", description="События с даты")
    ] = None,
    to: Annotated[datetime | None, Query(description="События до даты")] = None,
    sort: Annotated[
        str | None, Query(description="Сортировка: title, -title, created_at")
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedResponse[EventListItem]:
    """Список событий текущей организации с фильтрами."""
    svc = _build_event_service(session)
    offset = (page - 1) * per_page

    events, total = await svc.list_for_organizer(
        org_id=org.id,
        status=status,
        search=search,
        from_date=from_,
        to_date=to,
        sort=sort,
        limit=per_page,
        offset=offset,
    )

    items = [build_event_list_item(e) for e in events]
    return PaginatedResponse[EventListItem](
        items=items,
        pagination=Pagination.build(page=page, per_page=per_page, total=total),
    )


@router.get(
    "/{event_id}",
    response_model=EventDetailResponse,
    summary="Детали события",
    description="Полная информация о событии, включая тарифы.",
)
async def get_event(
    event_id: UUID,
    user: OrganizerUser,
    org: CurrentOrganization,
    session: SessionDep,
) -> EventDetailResponse:
    """Получить детальную информацию о событии.

    Tenant isolation: проверка через get_with_tariffs_for_org.
    Если событие не найдено ИЛИ принадлежит другой org — 404.
    """
    return await _require_event_for_org(session, event_id, org.id)


@router.patch(
    "/{event_id}",
    response_model=EventDetailResponse,
    summary="Обновить событие",
    description=(
        "PATCH-семантика: обновляются только переданные поля. "
        "В статусе published разрешены только безопасные поля "
        "(описание, изображения, локация)."
    ),
)
async def update_event(
    event_id: UUID,
    data: EventUpdateRequest,
    user: OrganizerUser,
    org: CurrentOrganization,
    session: SessionDep,
) -> EventDetailResponse:
    """Обновить событие (PATCH).

    Tenant isolation: событие должно принадлежать current org, иначе 404.
    """
    # Проверка принадлежности события организации
    event_repo = EventRepository(session)
    event = await event_repo.get_with_tariffs_for_org(event_id, org.id)
    if event is None:
        raise NotFoundError("Событие не найдено", details={"event_id": str(event_id)})

    svc = _build_event_service(session)
    unset_data = data.model_dump(exclude_unset=True)

    schedule_raw = unset_data.get("schedule")
    capacity_raw = unset_data.get("capacity_policy")
    fields_raw = unset_data.get("custom_fields_schema")

    event = await svc.update(
        event_id=event_id,
        data=UpdateEventInput(
            title=unset_data.get("title"),
            description_md=unset_data.get("description_md"),
            location_name=unset_data.get("location_name"),
            location_address=unset_data.get("location_address"),
            location_lat=unset_data.get("location_lat"),
            location_lng=unset_data.get("location_lng"),
            schedule=_safe_serialize_pydantic(schedule_raw),
            capacity_policy=_safe_serialize_pydantic(capacity_raw),
            custom_fields_schema=_safe_serialize_fields(fields_raw),
        ),
        by_user=user,
    )

    tariffs = getattr(event, "tariffs", []) or []
    return build_event_detail(event, tariffs)


@router.delete(
    "/{event_id}",
    response_model=OkResponse,
    summary="Архивировать событие",
    description="Soft-delete через перевод статуса в archived.",
)
async def archive_event(
    event_id: UUID,
    user: OrganizerUser,
    org: CurrentOrganization,
    session: SessionDep,
) -> OkResponse:
    """Архивировать событие (soft-delete).

    Tenant isolation: событие должно принадлежать current org, иначе 404.
    """
    event_repo = EventRepository(session)
    event = await event_repo.get_for_org(event_id, org.id)
    if event is None:
        raise NotFoundError("Событие не найдено", details={"event_id": str(event_id)})

    svc = _build_event_service(session)
    await svc.archive(event_id)
    return OkResponse()


@router.post(
    "/{event_id}/submit",
    response_model=EventDetailResponse,
    summary="Отправить на модерацию",
    description="Переводит событие из draft в pending_moderation.",
)
async def submit_event(
    event_id: UUID,
    user: OrganizerUser,
    org: CurrentOrganization,
    session: SessionDep,
) -> EventDetailResponse:
    """Отправить событие на модерацию.

    Tenant isolation: событие должно принадлежать current org, иначе 404.
    """
    event_repo = EventRepository(session)
    event = await event_repo.get_with_tariffs_for_org(event_id, org.id)
    if event is None:
        raise NotFoundError("Событие не найдено", details={"event_id": str(event_id)})

    svc = _build_event_service(session)
    event = await svc.submit_for_moderation(event_id)
    tariffs = getattr(event, "tariffs", []) or []
    return build_event_detail(event, tariffs)


@router.post(
    "/{event_id}/publish",
    response_model=EventDetailResponse,
    summary="Опубликовать событие",
    description=(
        "Публикует событие из pending_moderation в published. "
        "Organizer может опубликовать только если auto_publish_enabled=true."
    ),
)
async def publish_event(
    event_id: UUID,
    user: OrganizerUser,
    org: CurrentOrganization,
    session: SessionDep,
) -> EventDetailResponse:
    """Опубликовать событие.

    Tenant isolation: событие должно принадлежать current org, иначе 404.
    """
    event_repo = EventRepository(session)
    event = await event_repo.get_with_tariffs_for_org(event_id, org.id)
    if event is None:
        raise NotFoundError("Событие не найдено", details={"event_id": str(event_id)})

    svc = _build_event_service(session)
    event = await svc.publish(event_id, by_user=user)
    tariffs = getattr(event, "tariffs", []) or []
    return build_event_detail(event, tariffs)


@router.post(
    "/{event_id}/images",
    summary="Загрузить изображение события",
    description=(
        "Принимает multipart/form-data с полями: file (изображение) "
        "и kind (card или background). Возвращает публичный URL."
    ),
)
async def upload_event_image(
    event_id: UUID,
    file: Annotated[
        UploadFile,
        File(description="Изображение (JPEG, PNG, WebP, max 5MB)"),
    ],
    kind: Annotated[
        str,
        Form(description="Тип изображения: 'card' или 'background'"),
    ],
    user: OrganizerUser,
    org: CurrentOrganization,
    session: SessionDep,
) -> dict[str, str]:
    """Загрузить изображение события в S3.

    Tenant isolation: событие должно принадлежать current org, иначе 404.
    """
    event_repo = EventRepository(session)
    event = await event_repo.get_for_org(event_id, org.id)
    if event is None:
        raise NotFoundError("Событие не найдено", details={"event_id": str(event_id)})

    svc = _build_event_service(session)

    content = await file.read()
    content_type = file.content_type or "image/jpeg"

    url = await svc.upload_image(
        event_id=event_id,
        file_content=content,
        filename=file.filename or "image",
        content_type=content_type,
        kind=kind,
    )

    return {"url": url, "kind": kind}
