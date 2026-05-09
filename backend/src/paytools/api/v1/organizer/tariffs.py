"""Эндпоинты организатора: управление тарифами.

GET    /organizer/events/{event_id}/tariffs  — список тарифов события
POST   /organizer/events/{event_id}/tariffs  — создать тариф
PATCH  /organizer/tariffs/{id}               — обновить тариф
DELETE /organizer/tariffs/{id}               — удалить тариф
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from paytools.api.v1.deps import CurrentOrganization, OrganizerUser, SessionDep
from paytools.api.v1.schemas.tariff import (
    TariffCreateRequest,
    TariffDeleteResponse,
    TariffResponse,
    TariffUpdateRequest,
)
from paytools.core.errors import NotFoundError
from paytools.db.repositories.event import EventRepository
from paytools.db.repositories.tariff import TariffRepository
from paytools.domain.tariffs.service import (
    CreateTariffInput,
    TariffService,
    UpdateTariffInput,
)

router = APIRouter()


def _build_tariff_service(session: AsyncSession) -> TariffService:
    """Собрать TariffService с репозиториями."""
    tariff_repo = TariffRepository(session)
    event_repo = EventRepository(session)
    return TariffService(
        session,
        tariff_repo=tariff_repo,
        event_repo=event_repo,
    )


# --- Tenant isolation helpers ---


async def _require_event_belongs_to_org(
    session: AsyncSession, event_id: UUID, org_id: UUID
) -> None:
    """Проверить, что событие принадлежит организации.

    Если событие не найдено ИЛИ принадлежит другой org — 404.
    """
    event_repo = EventRepository(session)
    event = await event_repo.get_for_org(event_id, org_id)
    if event is None:
        raise NotFoundError("Событие не найдено", details={"event_id": str(event_id)})


async def _require_tariff_belongs_to_org(
    session: AsyncSession, tariff_id: UUID, org_id: UUID
) -> None:
    """Проверить, что тариф принадлежит организации.

    Если тариф не найден ИЛИ принадлежит другой org — 404.
    """
    tariff_repo = TariffRepository(session)
    tariff = await tariff_repo.get_for_org(tariff_id, org_id)
    if tariff is None:
        raise NotFoundError("Тариф не найден", details={"tariff_id": str(tariff_id)})


# --- CRUD ---


@router.get(
    "/events/{event_id}/tariffs",
    response_model=list[TariffResponse],
    summary="Список тарифов события",
    description="Возвращает все тарифы события, отсортированные по sort_order.",
)
async def list_tariffs(
    event_id: UUID,
    user: OrganizerUser,
    org: CurrentOrganization,
    session: SessionDep,
) -> list[TariffResponse]:
    """Список тарифов события.

    Tenant isolation: событие должно принадлежать current org, иначе 404.
    """
    await _require_event_belongs_to_org(session, event_id, org.id)
    svc = _build_tariff_service(session)
    tariffs = await svc.list_for_event(event_id)
    return [TariffResponse.model_validate(t) for t in tariffs]


@router.post(
    "/events/{event_id}/tariffs",
    response_model=TariffResponse,
    status_code=201,
    summary="Создать тариф",
    description=(
        "Создаёт тариф для события. Событие должно быть в статусе draft или published."
    ),
)
async def create_tariff(
    event_id: UUID,
    data: TariffCreateRequest,
    user: OrganizerUser,
    org: CurrentOrganization,
    session: SessionDep,
) -> TariffResponse:
    """Создать тариф для события.

    Tenant isolation: событие должно принадлежать current org, иначе 404.
    """
    await _require_event_belongs_to_org(session, event_id, org.id)

    svc = _build_tariff_service(session)
    tariff = await svc.create(
        event_id=event_id,
        org_id=org.id,
        data=CreateTariffInput(
            name=data.name,
            price_kopecks=data.price_kopecks,
            description=data.description,
            capacity_limit=data.capacity_limit,
            is_complimentary=data.is_complimentary,
            sort_order=data.sort_order,
            is_active=data.is_active,
        ),
    )

    return TariffResponse.model_validate(tariff)


@router.patch(
    "/tariffs/{tariff_id}",
    response_model=TariffResponse,
    summary="Обновить тариф",
    description=(
        "PATCH-семантика. Запрещено менять price_kopecks если есть "
        "проданные билеты по этому тарифу."
    ),
)
async def update_tariff(
    tariff_id: UUID,
    data: TariffUpdateRequest,
    user: OrganizerUser,
    org: CurrentOrganization,
    session: SessionDep,
) -> TariffResponse:
    """Обновить тариф (PATCH).

    Tenant isolation: тариф должен принадлежать current org, иначе 404.
    """
    await _require_tariff_belongs_to_org(session, tariff_id, org.id)

    svc = _build_tariff_service(session)
    unset_data = data.model_dump(exclude_unset=True)
    tariff = await svc.update(
        tariff_id=tariff_id,
        data=UpdateTariffInput(
            name=unset_data.get("name"),
            description=unset_data.get("description"),
            price_kopecks=unset_data.get("price_kopecks"),
            capacity_limit=unset_data.get("capacity_limit"),
            is_complimentary=unset_data.get("is_complimentary"),
            sort_order=unset_data.get("sort_order"),
            is_active=unset_data.get("is_active"),
        ),
    )

    return TariffResponse.model_validate(tariff)


@router.delete(
    "/tariffs/{tariff_id}",
    response_model=TariffDeleteResponse,
    summary="Удалить тариф",
    description=(
        "Soft delete (is_active=false) если есть проданные билеты, "
        "hard delete если нет."
    ),
)
async def delete_tariff(
    tariff_id: UUID,
    user: OrganizerUser,
    org: CurrentOrganization,
    session: SessionDep,
) -> TariffDeleteResponse:
    """Удалить тариф (soft/hard).

    Tenant isolation: тариф должен принадлежать current org, иначе 404.
    """
    await _require_tariff_belongs_to_org(session, tariff_id, org.id)

    svc = _build_tariff_service(session)
    result = await svc.delete(tariff_id)
    return TariffDeleteResponse(
        deleted=bool(result["deleted"]),
        method=str(result["method"]),
        tariff_id=tariff_id,
    )
