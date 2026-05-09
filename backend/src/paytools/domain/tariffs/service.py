"""Сервисный слой управления тарифами."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from paytools.db.models.enums import EventStatus
from paytools.db.models.event import Tariff
from paytools.db.repositories.event import EventRepository
from paytools.db.repositories.tariff import TariffRepository
from paytools.domain.tariffs.errors import (
    EventNotEditableForTariffError,
    TariffNotFoundError,
    TariffPriceLockedError,
)


@dataclass(slots=True, kw_only=True)
class CreateTariffInput:
    """Данные для создания тарифа."""

    name: str
    price_kopecks: int
    description: str | None = None
    capacity_limit: int | None = None
    is_complimentary: bool = False
    sort_order: int = 0
    is_active: bool = True


@dataclass(slots=True, kw_only=True)
class UpdateTariffInput:
    """Данные для обновления тарифа (PATCH-семантика)."""

    name: str | None = None
    description: str | None = None
    price_kopecks: int | None = None
    capacity_limit: int | None = None
    is_complimentary: bool | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class TariffService:
    """Доменный сервис управления тарифами."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        tariff_repo: TariffRepository,
        event_repo: EventRepository,
    ) -> None:
        self.session = session
        self.tariff_repo = tariff_repo
        self.event_repo = event_repo

    async def create(
        self, event_id: UUID, org_id: UUID, data: CreateTariffInput
    ) -> Tariff:
        """Создать тариф для события.

        Валидация:
        - Событие в статусе draft или published
        - price_kopecks ≥ 0
        - capacity_limit ≥ 0 если задан
        """
        event = await self.event_repo.get(event_id)
        if event is None:
            raise TariffNotFoundError(
                message="Событие не найдено",
                details={"event_id": str(event_id)},
            )
        if event.status not in (EventStatus.DRAFT, EventStatus.PUBLISHED):
            raise EventNotEditableForTariffError(
                details={"event_status": event.status.value}
            )

        if data.price_kopecks < 0:
            raise ValueError("price_kopecks не может быть отрицательным")

        if data.capacity_limit is not None and data.capacity_limit < 0:
            raise ValueError("capacity_limit не может быть отрицательным")

        tariff = await self.tariff_repo.create(
            event_id=event_id,
            organization_id=org_id,
            name=data.name,
            description=data.description,
            price_kopecks=data.price_kopecks,
            capacity_limit=data.capacity_limit,
            is_complimentary=data.is_complimentary,
            sort_order=data.sort_order,
            is_active=data.is_active,
        )
        return tariff

    async def update(self, tariff_id: UUID, data: UpdateTariffInput) -> Tariff:
        """Обновить тариф (PATCH-семантика).

        Запрет менять price_kopecks если уже есть проданные билеты.
        """
        tariff = await self._require_tariff(tariff_id)

        # Проверяем, можно ли редактировать событие
        event = await self.event_repo.get(tariff.event_id)
        if event is None:
            raise EventNotEditableForTariffError(
                message="Событие не найдено",
                details={"event_id": str(tariff.event_id)},
            )
        if event.status not in (EventStatus.DRAFT, EventStatus.PUBLISHED):
            raise EventNotEditableForTariffError(
                details={"event_status": event.status.value}
            )

        # Запрет изменения цены при проданных билетах
        if (
            data.price_kopecks is not None
            and data.price_kopecks != tariff.price_kopecks
        ):
            if await self.tariff_repo.has_sold_tickets(tariff_id):
                raise TariffPriceLockedError(details={"tariff_id": str(tariff_id)})

        # Обновляем переданные поля
        fields: list[tuple[str, object | None]] = [
            ("name", data.name),
            ("description", data.description),
            ("price_kopecks", data.price_kopecks),
            ("capacity_limit", data.capacity_limit),
            ("is_complimentary", data.is_complimentary),
            ("sort_order", data.sort_order),
            ("is_active", data.is_active),
        ]

        for field_name, value in fields:
            if value is not None:
                setattr(tariff, field_name, value)

        await self.session.flush()
        await self.session.refresh(tariff)
        return tariff

    async def delete(self, tariff_id: UUID) -> dict[str, object]:
        """Удалить тариф.

        Если есть проданные билеты — soft delete (is_active=False).
        Если нет — hard delete.
        """
        tariff = await self._require_tariff(tariff_id)

        if await self.tariff_repo.has_sold_tickets(tariff_id):
            # Soft delete
            tariff.is_active = False
            await self.session.flush()
            return {"deleted": True, "method": "soft", "tariff_id": str(tariff_id)}

        # Hard delete
        await self.session.delete(tariff)
        await self.session.flush()
        return {"deleted": True, "method": "hard", "tariff_id": str(tariff_id)}

    async def list_for_event(self, event_id: UUID) -> list[Tariff]:
        """Список тарифов события."""
        return await self.tariff_repo.list_for_event(event_id)

    async def list_active_for_event(self, event_id: UUID) -> list[Tariff]:
        """Список активных тарифов события (для публичной витрины)."""
        return await self.tariff_repo.list_active_for_event(event_id)

    # ----------------------------------------------------------------------- #
    # Приватные хелперы
    # ----------------------------------------------------------------------- #

    async def _require_tariff(self, tariff_id: UUID) -> Tariff:
        """Загрузить тариф или выбросить TariffNotFoundError."""
        tariff = await self.tariff_repo.get(tariff_id)
        if tariff is None:
            raise TariffNotFoundError(details={"tariff_id": str(tariff_id)})
        return tariff
