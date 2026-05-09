"""Сервисный слой бронирований."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from paytools.db.models.enums import EventStatus, ReservationStatus
from paytools.db.models.event import Tariff
from paytools.db.models.reservation import Reservation
from paytools.db.repositories.email_blocklist import EmailBlocklistRepository
from paytools.db.repositories.event import EventRepository
from paytools.db.repositories.promocode import (
    PromoCodeRepository,
    PromoCodeUsageRepository,
)
from paytools.db.repositories.reservation import ReservationRepository
from paytools.domain.bookings.errors import (
    CapacityExceededError,
    ConsentRequiredError,
    EmailBlockedError,
    EventNotPublishedError,
    ReservationAlreadyCancelledError,
    ReservationExpiredError,
    ReservationNotFoundError,
    TariffNotAvailableError,
)
from paytools.domain.promocodes.service import PromoService, ReservationItemInput

# Время жизни брони по умолчанию (минуты)
RESERVATION_TTL_MINUTES = 15


@dataclass(slots=True, kw_only=True)
class ReservationItemData:
    """Элемент бронирования из запроса."""

    tariff_id: UUID
    quantity: int


@dataclass(slots=True, kw_only=True)
class CreateReservationInput:
    """Данные для создания бронирования."""

    event_id: UUID
    session_id: UUID | None = None
    first_name: str
    last_name: str
    email: str
    phone: str
    items: list[ReservationItemData]
    custom_fields: dict[str, object] | None = None
    promo_code: str | None = None
    referrer_code: str | None = None
    consent_privacy: bool = False
    consent_offer: bool = False
    idempotency_key: str | None = None
    user_agent: str | None = None
    ip: str | None = None


class BookingService:
    """Доменный сервис бронирований.

    Ответственность:
    - Создание брони с проверкой capacity, email blocklist, promo codes
    - Отмена и истечение бронирований с компенсацией capacity/promo
    - Списки для организатора
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        reservation_repo: ReservationRepository,
        event_repo: EventRepository,
        promo_repo: PromoCodeRepository,
        usage_repo: PromoCodeUsageRepository,
        blocklist_repo: EmailBlocklistRepository,
    ) -> None:
        self.session = session
        self.reservation_repo = reservation_repo
        self.event_repo = event_repo
        self.promo_service = PromoService(
            session,
            promo_repo=promo_repo,
            usage_repo=usage_repo,
        )
        self.blocklist_repo = blocklist_repo

    async def create_reservation(
        self,
        org_id: UUID,
        data: CreateReservationInput,
    ) -> Reservation:
        """Создать бронирование.

        Полный flow:
        1. Idempotency check
        2. Согласия (consent)
        3. Email blocklist
        4. Событие published?
        5. Тарифы принадлежат событию и активны?
        6. Расчёт subtotal
        7. Промокод (если есть)
        8. Atomic capacity check
        9. Создание Reservation + ReservationItems
        """
        # 1. Idempotency
        if data.idempotency_key:
            existing = await self.reservation_repo.get_by_idempotency_key(
                data.idempotency_key
            )
            if existing is not None:
                return existing

        # 2. Согласия
        if not data.consent_privacy or not data.consent_offer:
            raise ConsentRequiredError()

        # 3. Email blocklist
        if await self.blocklist_repo.is_blocked(data.email):
            raise EmailBlockedError(
                details={"email": data.email}
            )

        # 4. Загрузить событие с тарифами
        event = await self.event_repo.get_with_tariffs(data.event_id)
        if event is None:
            raise EventNotPublishedError(
                details={"event_id": str(data.event_id)}
            )
        if event.status != EventStatus.PUBLISHED:
            raise EventNotPublishedError(
                details={"event_id": str(data.event_id), "status": event.status.value}
            )

        # 5. Валидация тарифов
        tariff_map: dict[UUID, Tariff] = {t.id: t for t in event.tariffs}
        for item in data.items:
            tariff = tariff_map.get(item.tariff_id)
            if tariff is None:
                raise TariffNotAvailableError(
                    details={"tariff_id": str(item.tariff_id), "reason": "not_found"}
                )
            if not tariff.is_active:
                raise TariffNotAvailableError(
                    details={"tariff_id": str(item.tariff_id), "reason": "inactive"}
                )

        # 6. Расчёт subtotal
        items_subtotal = 0
        promo_items: list[ReservationItemInput] = []
        for item in data.items:
            tariff = tariff_map[item.tariff_id]
            item_subtotal = tariff.price_kopecks * item.quantity
            items_subtotal += item_subtotal
            promo_items.append(
                ReservationItemInput(
                    tariff_id=item.tariff_id,
                    quantity=item.quantity,
                    price_kopecks=tariff.price_kopecks,
                )
            )

        # 7. Промокод
        discount_kopecks = 0
        promo_code_id: UUID | None = None

        # Сначала создаём reservation без promo (нужен ID для promo_code_usages)
        now = datetime.now(UTC)
        total_kopecks = items_subtotal  # Пока без скидки

        reservation = await self.reservation_repo.create_reservation(
            organization_id=org_id,
            event_id=data.event_id,
            session_id=data.session_id,
            first_name=data.first_name,
            last_name=data.last_name,
            email=data.email,
            phone=data.phone,
            custom_fields_data=data.custom_fields,
            items_subtotal_kopecks=items_subtotal,
            discount_kopecks=0,
            total_kopecks=total_kopecks,
            referrer_code=data.referrer_code,
            status=ReservationStatus.PENDING_PAYMENT,
            expires_at=now + timedelta(minutes=RESERVATION_TTL_MINUTES),
            consent_privacy=data.consent_privacy,
            consent_offer=data.consent_offer,
            idempotency_key=data.idempotency_key,
            user_agent=data.user_agent,
            ip=data.ip,
        )

        # Применяем промокод (нужен reservation_id)
        if data.promo_code:
            try:
                promo, discount_kopecks = await self.promo_service.apply(
                    org_id=org_id,
                    reservation_id=reservation.id,
                    code=data.promo_code,
                    event_id=data.event_id,
                    email=data.email,
                    items=promo_items,
                )
                promo_code_id = promo.id
                total_kopecks = max(0, items_subtotal - discount_kopecks)

                # Обновляем reservation
                reservation.promo_code_id = promo_code_id
                reservation.discount_kopecks = discount_kopecks
                reservation.total_kopecks = total_kopecks
            except Exception:
                # Если промокод невалиден — откатываем бронь
                await self.session.delete(reservation)
                await self.session.flush()
                raise

        # 8. Atomic capacity check
        total_qty = sum(item.quantity for item in data.items)
        capacity_policy = event.capacity_policy
        capacity_type = capacity_policy.get("type", "unlimited")

        try:
            if capacity_type == "total":
                limit = int(capacity_policy["limit"])
                success = await self.reservation_repo.atomic_increment_event_sold(
                    event.id, total_qty, limit
                )
                if not success:
                    raise CapacityExceededError(
                        details={"event_id": str(event.id), "requested": total_qty}
                    )

            elif capacity_type == "per_tariff":
                for item in data.items:
                    success = await self.reservation_repo.atomic_increment_tariff_sold(
                        item.tariff_id, item.quantity
                    )
                    if not success:
                        # Компенсация уже увеличенных тарифов
                        for prev_item in data.items:
                            if prev_item.tariff_id == item.tariff_id:
                                break
                            await self.reservation_repo.atomic_decrement_tariff_sold(
                                prev_item.tariff_id, prev_item.quantity
                            )
                        raise CapacityExceededError(
                            details={
                                "tariff_id": str(item.tariff_id),
                                "requested": item.quantity,
                            }
                        )

            elif capacity_type == "hybrid":
                # Проверяем и total, и per_tariff
                total_limit = int(capacity_policy.get("total", 0))
                if total_limit > 0:
                    success = await self.reservation_repo.atomic_increment_event_sold(
                        event.id, total_qty, total_limit
                    )
                    if not success:
                        raise CapacityExceededError(
                            details={"event_id": str(event.id), "requested": total_qty}
                        )
                for item in data.items:
                    success = await self.reservation_repo.atomic_increment_tariff_sold(
                        item.tariff_id, item.quantity
                    )
                    if not success:
                        # Компенсация
                        if total_limit > 0:
                            await self.reservation_repo.atomic_decrement_event_sold(
                                event.id, total_qty
                            )
                        for prev_item in data.items:
                            if prev_item.tariff_id == item.tariff_id:
                                break
                            await self.reservation_repo.atomic_decrement_tariff_sold(
                                prev_item.tariff_id, prev_item.quantity
                            )
                        raise CapacityExceededError(
                            details={
                                "tariff_id": str(item.tariff_id),
                                "requested": item.quantity,
                            }
                        )
            # unlimited — ничего не делаем

        except CapacityExceededError:
            # Откатываем промокод и бронь
            if promo_code_id:
                await self.promo_service.compensate(reservation.id, promo_code_id)
            await self.session.delete(reservation)
            await self.session.flush()
            raise

        # 9. Создание ReservationItems
        for item in data.items:
            tariff = tariff_map[item.tariff_id]
            await self.reservation_repo.create_item(
                reservation_id=reservation.id,
                tariff_id=item.tariff_id,
                quantity=item.quantity,
                price_kopecks=tariff.price_kopecks,
                subtotal_kopecks=tariff.price_kopecks * item.quantity,
            )

        await self.session.flush()

        # Перечитываем с items
        result = await self.reservation_repo.get_with_items(reservation.id)
        return result or reservation

    async def cancel(
        self,
        reservation_id: UUID,
        reason: str | None = None,
    ) -> Reservation:
        """Отменить бронирование с компенсацией capacity и промокода."""
        reservation = await self.reservation_repo.get_with_items(reservation_id)
        if reservation is None:
            raise ReservationNotFoundError(
                details={"reservation_id": str(reservation_id)}
            )

        if reservation.status == ReservationStatus.CANCELLED:
            raise ReservationAlreadyCancelledError()

        if reservation.status == ReservationStatus.EXPIRED:
            raise ReservationExpiredError()

        # Компенсация capacity
        await self._compensate_capacity(reservation)

        # Компенсация промокода
        if reservation.promo_code_id:
            await self.promo_service.compensate(
                reservation.id, reservation.promo_code_id
            )

        # Обновляем статус
        now = datetime.now(UTC)
        reservation.status = ReservationStatus.CANCELLED
        reservation.cancelled_at = now
        reservation.cancel_reason = reason

        await self.session.flush()
        return reservation

    async def expire_drafts(self) -> int:
        """Истечь все pending_payment брони с expires_at < now.

        Возвращает количество обработанных бронирований.
        Вызывается arq cron-задачей раз в минуту.
        """
        now = datetime.now(UTC)
        expired = await self.reservation_repo.find_expired_pending(now)

        count = 0
        for reservation in expired:
            # Компенсация capacity
            await self._compensate_capacity(reservation)

            # Компенсация промокода
            if reservation.promo_code_id:
                await self.promo_service.compensate(
                    reservation.id, reservation.promo_code_id
                )

            reservation.status = ReservationStatus.EXPIRED
            reservation.cancelled_at = now
            reservation.cancel_reason = "auto_expired"
            count += 1

        if count > 0:
            await self.session.flush()

        return count

    # --- Списки для организатора ---

    async def list_for_organizer(
        self,
        org_id: UUID,
        *,
        event_id: UUID | None = None,
        status: ReservationStatus | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Reservation], int]:
        """Список бронирований с пагинацией."""
        items = await self.reservation_repo.list_for_organizer(
            org_id,
            event_id=event_id,
            status_filter=status,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            offset=offset,
        )
        total = await self.reservation_repo.count_for_organizer(
            org_id,
            event_id=event_id,
            status_filter=status,
            from_date=from_date,
            to_date=to_date,
        )
        return items, total

    async def get(self, reservation_id: UUID) -> Reservation:
        """Получить бронирование."""
        reservation = await self.reservation_repo.get_with_items(reservation_id)
        if reservation is None:
            raise ReservationNotFoundError(
                details={"reservation_id": str(reservation_id)}
            )
        return reservation

    # --- Приватные хелперы ---

    async def _compensate_capacity(self, reservation: Reservation) -> None:
        """Компенсация capacity при отмене/истечении.

        Загружает событие, определяет capacity_policy и откатывает sold_count.
        """
        event = await self.event_repo.get(reservation.event_id)
        if event is None:
            return

        capacity_type = event.capacity_policy.get("type", "unlimited")
        items = reservation.items or []

        if capacity_type in ("total", "hybrid"):
            total_qty = sum(item.quantity for item in items)
            await self.reservation_repo.atomic_decrement_event_sold(
                event.id, total_qty
            )

        if capacity_type in ("per_tariff", "hybrid"):
            for item in items:
                await self.reservation_repo.atomic_decrement_tariff_sold(
                    item.tariff_id, item.quantity
                )
