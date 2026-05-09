"""Репозиторий для работы с промокодами (PromoCode, PromoCodeUsage)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from paytools.db.models.promocode import PromoCode, PromoCodeUsage
from paytools.db.repositories.base import BaseRepository


class PromoCodeRepository(BaseRepository[PromoCode]):
    """Репозиторий промокодов с tenant-фильтрацией."""

    model = PromoCode

    async def find_by_code(
        self, org_id: UUID, code: str
    ) -> PromoCode | None:
        """Поиск промокода по коду (case-insensitive) в рамках организации."""
        stmt = select(PromoCode).where(
            PromoCode.organization_id == org_id,
            func.upper(PromoCode.code) == code.upper(),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_code_for_update(
        self, org_id: UUID, code: str
    ) -> PromoCode | None:
        """Поиск промокода с блокировкой (FOR UPDATE) для атомарного инкремента."""
        stmt = (
            select(PromoCode)
            .where(
                PromoCode.organization_id == org_id,
                func.upper(PromoCode.code) == code.upper(),
            )
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def atomic_increment_used_count(self, promo_id: UUID) -> None:
        """Атомарно увеличить used_count на 1."""
        stmt = (
            update(PromoCode)
            .where(PromoCode.id == promo_id)
            .values(used_count=PromoCode.used_count + 1)
        )
        await self.session.execute(stmt)

    async def atomic_decrement_used_count(self, promo_id: UUID) -> None:
        """Компенсация: уменьшить used_count на 1."""
        stmt = (
            update(PromoCode)
            .where(PromoCode.id == promo_id)
            .values(used_count=func.greatest(PromoCode.used_count - 1, 0))
        )
        await self.session.execute(stmt)

    async def list_for_organizer(
        self,
        org_id: UUID,
        *,
        event_id: UUID | None = None,
        is_active: bool | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[PromoCode]:
        """Список промокодов организации."""
        stmt = select(PromoCode).where(PromoCode.organization_id == org_id)
        if event_id is not None:
            stmt = stmt.where(PromoCode.event_id == event_id)
        if is_active is not None:
            stmt = stmt.where(PromoCode.is_active == is_active)
        stmt = stmt.order_by(PromoCode.created_at.desc())
        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_for_organizer(
        self,
        org_id: UUID,
        *,
        event_id: UUID | None = None,
        is_active: bool | None = None,
    ) -> int:
        """Подсчёт промокодов организации."""
        stmt = (
            select(func.count())
            .select_from(PromoCode)
            .where(PromoCode.organization_id == org_id)
        )
        if event_id is not None:
            stmt = stmt.where(PromoCode.event_id == event_id)
        if is_active is not None:
            stmt = stmt.where(PromoCode.is_active == is_active)
        result = await self.session.execute(stmt)
        return int(result.scalar_one())


class PromoCodeUsageRepository(BaseRepository[PromoCodeUsage]):
    """Репозиторий использований промокода."""

    model = PromoCodeUsage

    async def count_by_email(self, promo_id: UUID, email: str) -> int:
        """Сколько раз email уже использовал данный промокод."""
        stmt = (
            select(func.count())
            .select_from(PromoCodeUsage)
            .where(
                PromoCodeUsage.promo_code_id == promo_id,
                func.lower(PromoCodeUsage.email) == email.lower(),
            )
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def create_usage(self, **data: Any) -> PromoCodeUsage:
        """Записать факт применения промокода."""
        usage = PromoCodeUsage(**data)
        self.session.add(usage)
        await self.session.flush()
        return usage

    async def delete_by_reservation(self, reservation_id: UUID) -> None:
        """Удалить записи использования по reservation_id (при компенсации)."""
        stmt = select(PromoCodeUsage).where(
            PromoCodeUsage.reservation_id == reservation_id
        )
        result = await self.session.execute(stmt)
        for usage in result.scalars().all():
            await self.session.delete(usage)
        await self.session.flush()

    async def list_for_promo(
        self,
        promo_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PromoCodeUsage]:
        """История применений конкретного промокода."""
        stmt = (
            select(PromoCodeUsage)
            .where(PromoCodeUsage.promo_code_id == promo_id)
            .order_by(PromoCodeUsage.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_for_promo(self, promo_id: UUID) -> int:
        """Подсчёт применений промокода."""
        stmt = (
            select(func.count())
            .select_from(PromoCodeUsage)
            .where(PromoCodeUsage.promo_code_id == promo_id)
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one())
