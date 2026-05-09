"""Репозиторий организаций."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from paytools.db.models.enums import OrganizationStatus
from paytools.db.models.organization import Organization
from paytools.db.repositories.base import BaseRepository


class OrganizationRepository(BaseRepository[Organization]):
    """Репозиторий для работы с организациями.

    Tenant-фильтр из BaseRepository не применяется, потому что модель
    Organization не имеет колонки organization_id —
    hasattr(self.model, "organization_id") возвращает False.
    Это корректно: организация сама является арендатором.
    """

    model = Organization

    async def get_by_slug(self, slug: str) -> Organization | None:
        """Поиск организации по slug.

        Slug нормализуется в lower при записи — прямое сравнение
        использует unique-индекс.
        """
        stmt = select(Organization).where(Organization.slug == slug.lower())
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, org_id: UUID) -> Organization | None:
        """Поиск организации по первичному ключу."""
        stmt = select(Organization).where(Organization.id == org_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def slug_exists(self, slug: str) -> bool:
        """Проверка, занят ли slug (slug уже нормализован в lower).

        Оптимизированный exists-check: выбираем константу и проверяем
        наличие результата. Прямое сравнение использует unique-индекс.
        """
        stmt = select(1).where(Organization.slug == slug.lower())
        result = await self.session.execute(stmt)
        return result.scalar() is not None

    async def list_by_status(
        self,
        status: OrganizationStatus,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Organization]:
        """Список организаций в заданном статусе (для админки модерации)."""
        stmt = (
            select(Organization)
            .where(Organization.status == status)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_with_users(
        self,
        *,
        status: OrganizationStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Organization]:
        """Список организаций с eager-загрузкой users (решает N+1)."""
        stmt = (
            select(Organization)
            .options(selectinload(Organization.users))
            .limit(limit)
            .offset(offset)
        )
        if status is not None:
            stmt = stmt.where(Organization.status == status)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_status(self, status: OrganizationStatus) -> int:
        """Количество организаций в заданном статусе."""
        stmt = (
            select(func.count())
            .select_from(Organization)
            .where(Organization.status == status)
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def set_status(
        self, org: Organization, new_status: OrganizationStatus
    ) -> None:
        """Изменить статус организации и сразу сбросить в БД.

        Только flush — commit и аудит-запись делает вызывающий сервис.
        """
        org.status = new_status
        await self.session.flush()
