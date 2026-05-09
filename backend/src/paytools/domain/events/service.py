"""Сервисный слой управления событиями.

Отвечает за CRUD событий, жизненный цикл (draft → published → archived),
загрузку изображений в S3 и публичный доступ.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from typing import Any
from uuid import UUID

from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from paytools.core.config import get_settings
from paytools.db.models.enums import EventStatus, UserRole
from paytools.db.models.event import Event
from paytools.db.models.user import User
from paytools.db.repositories.event import EventRepository
from paytools.db.repositories.organization import OrganizationRepository
from paytools.domain.events.errors import (
    CannotPublishError,
    EventNotEditableError,
    EventNotFoundError,
    ImageInvalidFormatError,
    ImageStorageError,
    ImageTooLargeError,
    ImageValidationError,
    InvalidStatusTransitionError,
    PublishedFieldsRestrictedError,
)
from paytools.domain.events.slug import make_unique_slug, slugify
from paytools.integrations.storage.s3 import S3Storage

# ---------------------------------------------------------------------------
# Входные DTO
# ---------------------------------------------------------------------------

ALLOWED_IMAGE_FORMATS = frozenset({"image/jpeg", "image/png", "image/webp"})
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB
MAX_IMAGE_WIDTH = 1920
MAX_IMAGE_HEIGHT = 1080


@dataclass(slots=True, kw_only=True)
class CreateEventInput:
    """Данные для создания события."""

    title: str
    slug: str | None  # None = автогенерация
    description_md: str | None = None
    location_name: str | None = None
    location_address: str | None = None
    location_lat: float | None = None
    location_lng: float | None = None
    schedule: dict[str, Any]
    capacity_policy: dict[str, Any]
    custom_fields_schema: list[dict[str, Any]] | None = None


@dataclass(slots=True, kw_only=True)
class UpdateEventInput:
    """Данные для обновления события.

    PATCH-семантика: передаём только то, что нужно обновить.
    Поля со значением None означают «передано и должно быть очищено».
    Отсутствие поля означает «не передано, оставить как есть».
    """

    title: str | None = None
    description_md: str | None = None
    location_name: str | None = None
    location_address: str | None = None
    location_lat: float | None = None
    location_lng: float | None = None
    schedule: dict[str, Any] | None = None
    capacity_policy: dict[str, Any] | None = None
    custom_fields_schema: list[dict[str, Any]] | None = None

    # Поля, разрешённые для published-событий
    _published_allowed = frozenset(
        {
            "title",
            "description_md",
            "location_name",
            "location_address",
            "location_lat",
            "location_lng",
            # image_card_url, image_background_url — управляются отдельными методами
        }
    )


# ---------------------------------------------------------------------------
# Сервис
# ---------------------------------------------------------------------------


class EventService:
    """Доменный сервис управления событиями.

    Не открывает и не коммитит транзакцию сам — работает внутри сессии,
    переданной из вызывающего слоя.
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        event_repo: EventRepository,
        org_repo: OrganizationRepository,
        s3_storage: S3Storage | None = None,
    ) -> None:
        self.session = session
        self.event_repo = event_repo
        self.org_repo = org_repo
        self.s3_storage = s3_storage
        self._settings = get_settings()

    # --- CRUD ---

    async def create(self, org_id: UUID, data: CreateEventInput) -> Event:
        """Создать событие в статусе draft.

        Slug генерируется из title если не передан; проверяется уникальность
        в рамках организации.
        """
        # Генерация slug
        slug = await self._generate_unique_slug(org_id, data.slug, data.title)

        event = await self.event_repo.create(
            organization_id=org_id,
            slug=slug,
            title=data.title,
            description_md=data.description_md,
            location_name=data.location_name,
            location_address=data.location_address,
            location_lat=data.location_lat,
            location_lng=data.location_lng,
            schedule=data.schedule,
            capacity_policy=data.capacity_policy,
            custom_fields_schema=data.custom_fields_schema,
            status=EventStatus.DRAFT,
        )
        return event

    async def update(
        self,
        event_id: UUID,
        data: UpdateEventInput,
        *,
        by_user: User,
    ) -> Event:
        """Обновить событие (PATCH-семантика).

        В draft — можно менять все поля.
        В published — только безопасные (описание, изображения, локация).
        Цены тарифов и schedule менять нельзя.
        """
        event = await self._require_event(event_id)
        self._validate_editable(event)

        updated = False

        _allowed = UpdateEventInput._published_allowed

        field_map: list[tuple[str, object | None]] = [
            ("title", data.title),
            ("description_md", data.description_md),
            ("location_name", data.location_name),
            ("location_address", data.location_address),
            ("location_lat", data.location_lat),
            ("location_lng", data.location_lng),
            ("schedule", data.schedule),
            ("capacity_policy", data.capacity_policy),
            ("custom_fields_schema", data.custom_fields_schema),
        ]

        for field_name, value in field_map:
            if value is not None or (
                field_name == "custom_fields_schema"
                and data.custom_fields_schema is not None
            ):
                if event.status == EventStatus.PUBLISHED and field_name not in _allowed:
                    raise PublishedFieldsRestrictedError(details={"field": field_name})
                setattr(event, field_name, value)
                updated = True

        if updated:
            await self.session.flush()
            await self.session.refresh(event)

        return event

    # --- Жизненный цикл ---

    async def submit_for_moderation(self, event_id: UUID) -> Event:
        """Отправить событие на модерацию: draft → pending_moderation."""
        event = await self._require_event(event_id)

        if event.status != EventStatus.DRAFT:
            raise InvalidStatusTransitionError(
                details={
                    "current": event.status.value,
                    "expected": EventStatus.DRAFT.value,
                    "target": EventStatus.PENDING_MODERATION.value,
                }
            )

        event.status = EventStatus.PENDING_MODERATION
        await self.session.flush()
        await self.session.refresh(event)
        return event

    async def publish(self, event_id: UUID, *, by_user: User) -> Event:
        """Опубликовать событие: pending_moderation → published.

        Superadmin может публиковать всегда (модерация).
        Organizer — только если organization.auto_publish_enabled = True.
        """
        event = await self._require_event(event_id)

        if event.status != EventStatus.PENDING_MODERATION:
            raise InvalidStatusTransitionError(
                details={
                    "current": event.status.value,
                    "expected": EventStatus.PENDING_MODERATION.value,
                    "target": EventStatus.PUBLISHED.value,
                }
            )

        # Проверка прав
        if by_user.role != UserRole.SUPERADMIN:
            org = await self.org_repo.get_by_id(event.organization_id)
            if org is None or not org.auto_publish_enabled:
                raise CannotPublishError(
                    details={
                        "auto_publish_enabled": False
                        if org is None
                        else org.auto_publish_enabled
                    }
                )

        event.status = EventStatus.PUBLISHED
        event.published_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.refresh(event)
        return event

    async def reject(self, event_id: UUID, *, note: str, by_user: User) -> Event:
        """Отклонить событие: pending_moderation → rejected с note.

        Только superadmin.
        """
        event = await self._require_event(event_id)

        if event.status != EventStatus.PENDING_MODERATION:
            raise InvalidStatusTransitionError(
                details={
                    "current": event.status.value,
                    "expected": EventStatus.PENDING_MODERATION.value,
                    "target": EventStatus.REJECTED.value,
                }
            )

        if by_user.role != UserRole.SUPERADMIN:
            raise CannotPublishError(
                message="Только superadmin может отклонять события"
            )

        event.status = EventStatus.REJECTED
        event.moderation_note = note
        await self.session.flush()
        await self.session.refresh(event)
        return event

    async def archive(self, event_id: UUID) -> None:
        """Архивировать событие (soft-delete через статус archived)."""
        event = await self._require_event(event_id)

        if event.status == EventStatus.ARCHIVED:
            return  # Идемпотентно

        event.status = EventStatus.ARCHIVED
        await self.session.flush()

    # --- Изображения ---

    async def upload_image(
        self,
        event_id: UUID,
        *,
        file_content: bytes,
        filename: str,
        content_type: str,
        kind: str,
    ) -> str:
        """Загрузить изображение события в S3, вернуть публичный URL.

        kind: 'card' или 'background'.
        Валидация формата и размера; resize до 1920x1080.
        """
        if kind not in ("card", "background"):
            raise ValueError(f"kind must be 'card' or 'background', got {kind!r}")

        event = await self._require_event(event_id)

        # Валидация формата
        if content_type not in ALLOWED_IMAGE_FORMATS:
            raise ImageInvalidFormatError(details={"content_type": content_type})

        # Валидация размера
        if len(file_content) > MAX_IMAGE_SIZE_BYTES:
            raise ImageTooLargeError(
                details={
                    "size_bytes": len(file_content),
                    "max_size_bytes": MAX_IMAGE_SIZE_BYTES,
                }
            )

        # Resize через Pillow
        try:
            img: Image.Image = Image.open(BytesIO(file_content))
            img = self._resize_image(img)
            output = BytesIO()
            save_format = self._get_pillow_format(content_type)
            img.save(output, format=save_format)
            processed_content = output.getvalue()
        except Exception as e:
            raise ImageValidationError(details={"error": str(e)}) from e

        # Определяем расширение файла
        ext = self._get_extension(content_type)

        # Ключ в S3: events/{org_id}/{event_id}/{kind}-{uuid}.{ext}
        import uuid

        object_key = (
            f"events/{event.organization_id}/{event.id}/{kind}-{uuid.uuid4()}.{ext}"
        )

        if self.s3_storage is None:
            raise ImageStorageError(
                message="S3-хранилище не настроено",
                details={"s3_storage": None},
            )

        try:
            await self.s3_storage.upload(
                key=object_key,
                data=processed_content,
                content_type=content_type,
            )
        except Exception as e:
            raise ImageStorageError(
                details={"error": str(e)},
            ) from e

        # Формируем публичный URL
        public_url = self.s3_storage.public_url(object_key)

        # Сохраняем URL в модели
        if kind == "card":
            event.image_card_url = public_url
        else:
            event.image_background_url = public_url

        await self.session.flush()
        await self.session.refresh(event)

        return public_url

    # --- Списки ---

    async def list_for_organizer(
        self,
        org_id: UUID,
        *,
        status: EventStatus | None = None,
        search: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        sort: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Event], int]:
        """Список событий организатора с фильтрами и пагинацией."""
        events = await self.event_repo.list_by_organization(
            org_id,
            status_filter=status,
            search=search,
            from_date=from_date,
            to_date=to_date,
            sort=sort,
            limit=limit,
            offset=offset,
        )
        total = await self.event_repo.count_by_organization(
            org_id,
            status_filter=status,
            search=search,
            from_date=from_date,
            to_date=to_date,
        )
        return events, total

    async def list_public(
        self,
        org_id: UUID,
        *,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        sort: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Event], int]:
        """Список опубликованных событий (публичная витрина)."""
        events = await self.event_repo.list_public(
            org_id,
            from_date=from_date,
            to_date=to_date,
            sort=sort,
            limit=limit,
            offset=offset,
        )
        total = await self.event_repo.count_public(
            org_id,
            from_date=from_date,
            to_date=to_date,
        )
        return events, total

    async def get_by_slug_public(self, org_id: UUID, slug: str) -> Event:
        """Получить опубликованное событие по slug."""
        event = await self.event_repo.get_by_slug(org_id, slug)
        if event is None:
            raise EventNotFoundError(
                details={"slug": slug, "organization_id": str(org_id)}
            )
        return event

    async def list_pending_moderation(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Event], int]:
        """Список событий на модерации (для админа)."""
        events = await self.event_repo.list_pending_moderation(
            limit=limit, offset=offset
        )
        total = await self.event_repo.count_pending_moderation()
        return events, total

    # ----------------------------------------------------------------------- #
    # Приватные хелперы
    # ----------------------------------------------------------------------- #

    async def _require_event(self, event_id: UUID) -> Event:
        """Загрузить событие или выбросить EventNotFoundError."""
        event = await self.event_repo.get_with_tariffs(event_id)
        if event is None:
            raise EventNotFoundError(details={"event_id": str(event_id)})
        return event

    def _validate_editable(self, event: Event) -> None:
        """Проверить, что событие можно редактировать.

        Редактировать можно только draft и published.
        """
        if event.status not in (EventStatus.DRAFT, EventStatus.PUBLISHED):
            raise EventNotEditableError(details={"current_status": event.status.value})

    async def _generate_unique_slug(
        self, org_id: UUID, provided_slug: str | None, title: str
    ) -> str:
        """Сгенерировать уникальный slug в рамках организации."""
        if provided_slug:
            base_slug = slugify(provided_slug)
        else:
            base_slug = slugify(title)

        # Проверяем уникальность
        slug = base_slug
        attempt = 2
        while await self.event_repo.slug_exists(org_id, slug):
            slug = make_unique_slug(base_slug, attempt)
            attempt += 1

        return slug

    @staticmethod
    def _resize_image(img: Image.Image) -> Image.Image:
        """Resize изображения до max 1920x1080 с сохранением aspect ratio."""
        if img.width <= MAX_IMAGE_WIDTH and img.height <= MAX_IMAGE_HEIGHT:
            return img
        img.thumbnail((MAX_IMAGE_WIDTH, MAX_IMAGE_HEIGHT), Image.Resampling.LANCZOS)
        return img

    @staticmethod
    def _get_pillow_format(content_type: str) -> str:
        """Маппинг MIME-типа на Pillow format."""
        mapping = {
            "image/jpeg": "JPEG",
            "image/png": "PNG",
            "image/webp": "WEBP",
        }
        return mapping.get(content_type, "JPEG")

    @staticmethod
    def _get_extension(content_type: str) -> str:
        """Маппинг MIME-типа на расширение файла."""
        mapping = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/webp": "webp",
        }
        return mapping.get(content_type, "jpg")
