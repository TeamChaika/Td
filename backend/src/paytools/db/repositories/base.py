"""Базовый репозиторий с автофильтром по organization_id."""

from __future__ import annotations

from typing import Any, TypeVar, cast
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from paytools.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository[ModelType: Base]:
    """Базовый репозиторий.

    Наследники обязаны задать `model: type[ModelType]`.
    Если модель имеет `organization_id`, и в репозиторий передан
    `organization_id`, все выборки автоматически фильтруются — это
    защищает от случайной утечки данных между арендаторами.
    """

    model: type[ModelType]

    def __init__(
        self, session: AsyncSession, organization_id: UUID | None = None
    ) -> None:
        self.session = session
        self.organization_id = organization_id

    def _apply_tenant_filter(self, stmt: Select[Any]) -> Select[Any]:
        """Добавляет фильтр по organization_id, если применимо."""
        if self.organization_id is not None and hasattr(self.model, "organization_id"):
            stmt = stmt.where(
                cast(Any, self.model).organization_id == self.organization_id
            )
        return stmt

    async def get(self, id: UUID) -> ModelType | None:
        """Найти по первичному ключу."""
        stmt = select(self.model).where(cast(Any, self.model).id == id)
        stmt = self._apply_tenant_filter(stmt)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(self, *, limit: int = 100, offset: int = 0) -> list[ModelType]:
        """Выдать страницу записей."""
        stmt = select(self.model).limit(limit).offset(offset)
        stmt = self._apply_tenant_filter(stmt)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count(self) -> int:
        """Подсчёт записей (с учётом tenant-фильтра)."""
        stmt = select(func.count()).select_from(self.model)
        stmt = self._apply_tenant_filter(stmt)
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def create(self, **data: Any) -> ModelType:
        """Создать запись. Если модель имеет `organization_id` и в репозитории
        задан `self.organization_id`, он подставится автоматически (если не
        передан явно в data)."""
        if (
            self.organization_id is not None
            and hasattr(self.model, "organization_id")
            and "organization_id" not in data
        ):
            data["organization_id"] = self.organization_id
        instance = self.model(**data)
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def delete(self, instance: ModelType) -> None:
        """Удалить запись."""
        await self.session.delete(instance)
        await self.session.flush()
