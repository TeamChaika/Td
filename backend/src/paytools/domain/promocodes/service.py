"""Сервисный слой управления промокодами."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from paytools.db.models.enums import DiscountType
from paytools.db.models.promocode import PromoCode
from paytools.db.repositories.promocode import (
    PromoCodeRepository,
    PromoCodeUsageRepository,
)
from paytools.domain.promocodes.errors import (
    PromoCodeDuplicateError,
    PromoCodeExpiredError,
    PromoCodeInactiveError,
    PromoCodeNotFoundError,
    PromoCodePerUserLimitError,
    PromoCodeUsageLimitError,
    PromoCodeWrongEventError,
    PromoCodeWrongTariffError,
)


@dataclass(slots=True, kw_only=True)
class ReservationItemInput:
    """Элемент брони для расчёта скидки."""

    tariff_id: UUID
    quantity: int
    price_kopecks: int


@dataclass(slots=True, kw_only=True)
class ValidationResult:
    """Результат валидации промокода."""

    valid: bool
    promo_code_id: UUID | None = None
    code: str = ""
    discount_type: DiscountType | None = None
    discount_value: int = 0
    discount_kopecks: int = 0
    description: str = ""
    error_code: str | None = None
    error_message: str | None = None


@dataclass(slots=True, kw_only=True)
class CreatePromoCodeInput:
    """Данные для создания промокода."""

    code: str
    description: str | None = None
    discount_type: DiscountType
    discount_value: int
    event_id: UUID | None = None
    tariff_id: UUID | None = None
    usage_limit: int | None = None
    per_user_limit: int | None = None
    active_from: datetime | None = None
    active_to: datetime | None = None
    is_active: bool = True
    is_affiliate: bool = False
    affiliate_user_id: UUID | None = None


@dataclass(slots=True, kw_only=True)
class UpdatePromoCodeInput:
    """Данные для обновления промокода (PATCH-семантика)."""

    description: str | None = None
    discount_type: DiscountType | None = None
    discount_value: int | None = None
    event_id: UUID | None = None
    tariff_id: UUID | None = None
    usage_limit: int | None = None
    per_user_limit: int | None = None
    active_from: datetime | None = None
    active_to: datetime | None = None
    is_active: bool | None = None


class PromoService:
    """Доменный сервис промокодов."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        promo_repo: PromoCodeRepository,
        usage_repo: PromoCodeUsageRepository,
    ) -> None:
        self.session = session
        self.promo_repo = promo_repo
        self.usage_repo = usage_repo

    async def validate(
        self,
        org_id: UUID,
        code: str,
        event_id: UUID,
        email: str,
        items: list[ReservationItemInput],
    ) -> ValidationResult:
        """Валидировать промокод без применения.

        Проверки:
        1. Код существует и принадлежит организации
        2. is_active = true
        3. active_from <= now <= active_to
        4. usage_limit не исчерпан
        5. per_user_limit не исчерпан (по email)
        6. event_id совпадает (если задан в промокоде)
        7. tariff_id совпадает (если задан в промокоде)
        """
        promo = await self.promo_repo.find_by_code(org_id, code)
        if promo is None:
            return ValidationResult(
                valid=False,
                error_code="promo_code_not_found",
                error_message="Промокод не найден",
            )

        # Проверка is_active
        if not promo.is_active:
            return ValidationResult(
                valid=False,
                error_code="promo_code_inactive",
                error_message="Промокод неактивен",
            )

        now = datetime.now(UTC)

        # Проверка временных границ
        if promo.active_from and now < promo.active_from:
            return ValidationResult(
                valid=False,
                error_code="promo_code_expired",
                error_message="Промокод ещё не начал действовать",
            )
        if promo.active_to and now > promo.active_to:
            return ValidationResult(
                valid=False,
                error_code="promo_code_expired",
                error_message="Промокод истёк",
            )

        # Проверка usage_limit
        if promo.usage_limit is not None and promo.used_count >= promo.usage_limit:
            return ValidationResult(
                valid=False,
                error_code="promo_code_usage_limit",
                error_message="Промокод исчерпал лимит использований",
            )

        # Проверка per_user_limit
        if promo.per_user_limit is not None:
            user_usage_count = await self.usage_repo.count_by_email(promo.id, email)
            if user_usage_count >= promo.per_user_limit:
                return ValidationResult(
                    valid=False,
                    error_code="promo_code_per_user_limit",
                    error_message=(
                        "Вы уже использовали этот промокод максимальное количество раз"
                    ),
                )

        # Проверка привязки к событию
        if promo.event_id is not None and promo.event_id != event_id:
            return ValidationResult(
                valid=False,
                error_code="promo_code_wrong_event",
                error_message="Промокод не действует для этого события",
            )

        # Проверка привязки к тарифу
        if promo.tariff_id is not None:
            item_tariff_ids = {item.tariff_id for item in items}
            if promo.tariff_id not in item_tariff_ids:
                return ValidationResult(
                    valid=False,
                    error_code="promo_code_wrong_tariff",
                    error_message="Промокод не действует для выбранных тарифов",
                )

        # Расчёт скидки
        discount_kopecks = self._calculate_discount(promo, items)

        return ValidationResult(
            valid=True,
            promo_code_id=promo.id,
            code=promo.code,
            discount_type=promo.discount_type,
            discount_value=promo.discount_value,
            discount_kopecks=discount_kopecks,
            description=promo.description or "",
        )

    async def apply(
        self,
        org_id: UUID,
        reservation_id: UUID,
        code: str,
        event_id: UUID,
        email: str,
        items: list[ReservationItemInput],
    ) -> tuple[PromoCode, int]:
        """Применить промокод к бронированию.

        1. Валидирует (все проверки)
        2. Блокирует строку FOR UPDATE
        3. Инкрементирует used_count
        4. Пишет в promo_code_usages
        5. Возвращает (promo, discount_kopecks)
        """
        # Валидируем
        result = await self.validate(org_id, code, event_id, email, items)
        if not result.valid:
            # Преобразуем ошибку валидации в соответствующий Exception
            self._raise_validation_error(result)

        # Блокируем строку для атомарного инкремента
        promo = await self.promo_repo.find_by_code_for_update(org_id, code)
        if promo is None:
            raise PromoCodeNotFoundError()

        # Повторная проверка usage_limit после блокировки (race condition protection)
        if promo.usage_limit is not None and promo.used_count >= promo.usage_limit:
            raise PromoCodeUsageLimitError()

        # Инкрементируем
        await self.promo_repo.atomic_increment_used_count(promo.id)

        # Записываем факт использования
        discount_kopecks = self._calculate_discount(promo, items)
        await self.usage_repo.create_usage(
            promo_code_id=promo.id,
            reservation_id=reservation_id,
            email=email,
            discount_kopecks=discount_kopecks,
        )

        return promo, discount_kopecks

    async def compensate(self, reservation_id: UUID, promo_id: UUID) -> None:
        """Компенсация: откатить применение промокода.

        Вызывается при отмене/истечении бронирования.
        """
        await self.promo_repo.atomic_decrement_used_count(promo_id)
        await self.usage_repo.delete_by_reservation(reservation_id)

    # --- CRUD для организатора ---

    async def create(
        self, org_id: UUID, data: CreatePromoCodeInput
    ) -> PromoCode:
        """Создать промокод."""
        # Проверяем уникальность кода в рамках организации
        existing = await self.promo_repo.find_by_code(org_id, data.code)
        if existing is not None:
            raise PromoCodeDuplicateError(
                details={"code": data.code}
            )

        return await self.promo_repo.create(
            organization_id=org_id,
            code=data.code.upper(),
            description=data.description,
            discount_type=data.discount_type,
            discount_value=data.discount_value,
            event_id=data.event_id,
            tariff_id=data.tariff_id,
            usage_limit=data.usage_limit,
            per_user_limit=data.per_user_limit,
            active_from=data.active_from,
            active_to=data.active_to,
            is_active=data.is_active,
            is_affiliate=data.is_affiliate,
            affiliate_user_id=data.affiliate_user_id,
        )

    async def update(
        self, promo_id: UUID, data: UpdatePromoCodeInput
    ) -> PromoCode:
        """Обновить промокод (PATCH-семантика)."""
        promo = await self.promo_repo.get(promo_id)
        if promo is None:
            raise PromoCodeNotFoundError(details={"promo_id": str(promo_id)})

        fields: list[tuple[str, object | None]] = [
            ("description", data.description),
            ("discount_type", data.discount_type),
            ("discount_value", data.discount_value),
            ("event_id", data.event_id),
            ("tariff_id", data.tariff_id),
            ("usage_limit", data.usage_limit),
            ("per_user_limit", data.per_user_limit),
            ("active_from", data.active_from),
            ("active_to", data.active_to),
            ("is_active", data.is_active),
        ]

        for field_name, value in fields:
            if value is not None:
                setattr(promo, field_name, value)

        await self.session.flush()
        await self.session.refresh(promo)
        return promo

    async def delete(self, promo_id: UUID) -> dict[str, object]:
        """Удалить промокод.

        Если есть использования — soft delete (is_active=False).
        Если нет — hard delete.
        """
        promo = await self.promo_repo.get(promo_id)
        if promo is None:
            raise PromoCodeNotFoundError(details={"promo_id": str(promo_id)})

        usage_count = await self.usage_repo.count_for_promo(promo_id)
        if usage_count > 0:
            # Soft delete
            promo.is_active = False
            await self.session.flush()
            return {"deleted": True, "method": "soft", "promo_id": str(promo_id)}

        # Hard delete
        await self.session.delete(promo)
        await self.session.flush()
        return {"deleted": True, "method": "hard", "promo_id": str(promo_id)}

    # --- Расчёт скидки ---

    @staticmethod
    def _calculate_discount(
        promo: PromoCode, items: list[ReservationItemInput]
    ) -> int:
        """Рассчитать скидку в копейках.

        - percent: subtotal * discount_value / 10000 (value хранится ×100)
        - fixed_amount: min(discount_value, subtotal)
        - fixed_price: разница между оригинальной ценой и discount_value за штуку
        """
        subtotal = sum(item.price_kopecks * item.quantity for item in items)

        if promo.discount_type == DiscountType.PERCENT:
            return subtotal * promo.discount_value // 10000

        if promo.discount_type == DiscountType.FIXED_AMOUNT:
            return min(promo.discount_value, subtotal)

        if promo.discount_type == DiscountType.FIXED_PRICE:
            # fixed_price действует на конкретный тариф
            discount = 0
            for item in items:
                if promo.tariff_id is None or item.tariff_id == promo.tariff_id:
                    original_per_item = item.price_kopecks
                    new_per_item = min(promo.discount_value, original_per_item)
                    discount += (original_per_item - new_per_item) * item.quantity
            return discount

        return 0

    @staticmethod
    def _raise_validation_error(result: ValidationResult) -> None:
        """Преобразовать невалидный ValidationResult в Exception."""
        error_map = {
            "promo_code_not_found": PromoCodeNotFoundError,
            "promo_code_inactive": PromoCodeInactiveError,
            "promo_code_expired": PromoCodeExpiredError,
            "promo_code_usage_limit": PromoCodeUsageLimitError,
            "promo_code_per_user_limit": PromoCodePerUserLimitError,
            "promo_code_wrong_event": PromoCodeWrongEventError,
            "promo_code_wrong_tariff": PromoCodeWrongTariffError,
        }
        error_cls = error_map.get(result.error_code or "", PromoCodeNotFoundError)
        raise error_cls(message=result.error_message)
