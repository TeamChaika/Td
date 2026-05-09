"""Репозиторий для работы с событиями (Event)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, func, or_, select
from sqlalchemy import cast as sa_cast
from sqlalchemy.orm import selectinload

from paytools.db.models.enums import EventStatus
from paytools.db.models.event import Event
from paytools.db.repositories.base import BaseRepository


def _schedule_starts() -> Any:
    """Извлечь starts_at из JSONB schedule как строку."""
    return Event.schedule["starts_at"].as_string()


def _cast_schedule_starts() -> Any:
    """Привести starts_at из JSONB к TIMESTAMPTZ для сравнения."""
    return sa_cast(_schedule_starts(), DateTime(timezone=True))


class EventRepository(BaseRepository[Event]):
    """Репозиторий событий с tenant-фильтрацией."""

    model = Event

    async def get_with_tariffs(self, event_id: UUID) -> Event | None:
        """Загрузить событие с eager-loading тарифов (решает N+1)."""
        stmt = (
            select(Event)
            .options(selectinload(Event.tariffs))
            .where(Event.id == event_id)
        )
        stmt = self._apply_tenant_filter(stmt)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_tariffs_for_org(
        self, event_id: UUID, org_id: UUID
    ) -> Event | None:
        """Загрузить событие с тарифами, явно фильтруя по org_id.

        Возвращает None, если событие не существует ИЛИ принадлежит другой org.
        Используется для проверки tenant isolation в organizer-эндпоинтах.
        """
        stmt = (
            select(Event)
            .options(selectinload(Event.tariffs))
            .where(Event.id == event_id, Event.organization_id == org_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_for_org(self, event_id: UUID, org_id: UUID) -> Event | None:
        """Загрузить событие (без тарифов), явно фильтруя по org_id.

        Возвращает None, если событие не существует ИЛИ принадлежит другой org.
        """
        stmt = select(Event).where(
            Event.id == event_id, Event.organization_id == org_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_organization(
        self,
        org_id: UUID,
        *,
        status_filter: EventStatus | None = None,
        search: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        sort: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Event]:
        """Список событий организации с фильтрами и пагинацией."""
        stmt = (
            select(Event)
            .options(selectinload(Event.tariffs))
            .where(Event.organization_id == org_id)
        )

        if status_filter is not None:
            stmt = stmt.where(Event.status == status_filter)
        if search:
            stmt = stmt.where(
                or_(
                    Event.title.ilike(f"%{search}%"),
                    Event.location_name.ilike(f"%{search}%"),
                )
            )
        if from_date is not None:
            stmt = stmt.where(_cast_schedule_starts() >= from_date)
        if to_date is not None:
            stmt = stmt.where(_cast_schedule_starts() <= to_date)

        if sort == "title":
            stmt = stmt.order_by(Event.title)
        elif sort == "-title":
            stmt = stmt.order_by(Event.title.desc())
        elif sort == "created_at":
            stmt = stmt.order_by(Event.created_at)
        else:
            stmt = stmt.order_by(Event.created_at.desc())

        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_organization(
        self,
        org_id: UUID,
        *,
        status_filter: EventStatus | None = None,
        search: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> int:
        """Количество событий организации с фильтрами."""
        stmt = (
            select(func.count())
            .select_from(Event)
            .where(Event.organization_id == org_id)
        )
        if status_filter is not None:
            stmt = stmt.where(Event.status == status_filter)
        if search:
            stmt = stmt.where(
                or_(
                    Event.title.ilike(f"%{search}%"),
                    Event.location_name.ilike(f"%{search}%"),
                )
            )
        if from_date is not None:
            stmt = stmt.where(_cast_schedule_starts() >= from_date)
        if to_date is not None:
            stmt = stmt.where(_cast_schedule_starts() <= to_date)
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def list_public(
        self,
        org_id: UUID,
        *,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        sort: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Event]:
        """Список опубликованных событий (для публичной витрины)."""
        stmt = (
            select(Event)
            .options(selectinload(Event.tariffs))
            .where(
                Event.organization_id == org_id,
                Event.status == EventStatus.PUBLISHED,
            )
        )

        if from_date is not None:
            stmt = stmt.where(_cast_schedule_starts() >= from_date)
        if to_date is not None:
            stmt = stmt.where(_cast_schedule_starts() <= to_date)

        # Сортировка: по умолчанию по starts_at
        if sort == "-schedule":
            stmt = stmt.order_by(_cast_schedule_starts().desc())
        else:
            stmt = stmt.order_by(_cast_schedule_starts())

        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_public(
        self,
        org_id: UUID,
        *,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> int:
        """Количество опубликованных событий."""
        stmt = (
            select(func.count())
            .select_from(Event)
            .where(
                Event.organization_id == org_id,
                Event.status == EventStatus.PUBLISHED,
            )
        )
        if from_date is not None:
            stmt = stmt.where(_cast_schedule_starts() >= from_date)
        if to_date is not None:
            stmt = stmt.where(_cast_schedule_starts() <= to_date)
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def get_by_slug(self, org_id: UUID, slug: str) -> Event | None:
        """Поиск опубликованного события по slug в рамках организации."""
        stmt = (
            select(Event)
            .options(selectinload(Event.tariffs))
            .where(
                Event.organization_id == org_id,
                Event.slug == slug,
                Event.status == EventStatus.PUBLISHED,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def slug_exists(self, org_id: UUID, slug: str) -> bool:
        """Проверка, существует ли событие с таким slug в организации."""
        stmt = select(1).where(
            Event.organization_id == org_id,
            Event.slug == slug,
        )
        result = await self.session.execute(stmt)
        return result.scalar() is not None

    async def list_pending_moderation(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Event]:
        """Список событий на модерации (со всех организаций, для админа)."""
        stmt = (
            select(Event)
            .options(selectinload(Event.tariffs))
            .where(Event.status == EventStatus.PENDING_MODERATION)
            .order_by(Event.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_pending_moderation(self) -> int:
        """Количество событий на модерации."""
        stmt = (
            select(func.count())
            .select_from(Event)
            .where(Event.status == EventStatus.PENDING_MODERATION)
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one())
