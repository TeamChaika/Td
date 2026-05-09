"""Репозиторий пользователей."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from paytools.db.models.user import User
from paytools.db.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Репозиторий для работы с пользователями."""

    model = User

    async def get_by_email(self, email: str) -> User | None:
        """Поиск пользователя по email (email нормализуется в lower при записи).

        Tenant-фильтр применяется (если репозиторий создан с organization_id),
        чтобы при администрировании конкретной организации не найти
        пользователя из другой.
        """
        stmt = select(User).where(User.email == email.lower())
        stmt = self._apply_tenant_filter(stmt)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: UUID) -> User | None:
        """Поиск пользователя по id без tenant-фильтра.

        Переопределён относительно base.get, потому что tenant-фильтр
        отсекает superadmin'ов с organization_id IS NULL —
        для них условие «organization_id == <конкретный uuid>» всегда ложно.
        """
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_organization(self, organization_id: UUID) -> list[User]:
        """Все пользователи, привязанные к конкретной организации.

        Tenant-фильтр не применяется: organisation_id передан явно,
        дополнительная фильтрация по self.organization_id избыточна
        и может конфликтовать (если репозиторий создан с другим org_id).
        """
        stmt = select(User).where(User.organization_id == organization_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_last_login(self, user: User) -> None:
        """Зафиксировать время последнего входа пользователя.

        Только flush — commit делает вызывающий сервис.
        """
        user.last_login_at = datetime.now(UTC)
        await self.session.flush()

    async def email_exists(self, email: str) -> bool:
        """Проверка, занят ли email любым пользователем.

        Email уже нормализован в lower при записи — прямое сравнение
        использует unique-индекс.
        """
        stmt = select(1).where(User.email == email.lower())
        result = await self.session.execute(stmt)
        return result.scalar() is not None
