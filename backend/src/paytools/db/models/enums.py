"""ENUM-ы доменной модели.

Каждый ENUM объявлен дважды: как Python `StrEnum` (для кода) и как
`postgresql.ENUM` (для БД). PG-ENUM используется при объявлении колонок
и в Alembic-миграциях.
"""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy.dialects.postgresql import ENUM as PgEnum


def _pg_enum(py_enum: type[StrEnum], name: str) -> PgEnum:
    """Обёртка: PG ENUM, где значения берутся из values_callable."""
    return PgEnum(
        py_enum,
        name=name,
        values_callable=lambda x: [e.value for e in x],
        create_type=True,
    )


# -------------------- Organization --------------------


class OrganizationStatus(StrEnum):
    PENDING_MODERATION = "pending_moderation"
    ACTIVE = "active"
    SUSPENDED = "suspended"


organization_status_enum = _pg_enum(OrganizationStatus, "organization_status")


class LegalEntityType(StrEnum):
    IP = "ip"
    OOO = "ooo"
    SELF_EMPLOYED = "self_employed"
    OTHER = "other"


legal_entity_type_enum = _pg_enum(LegalEntityType, "legal_entity_type")


# -------------------- User --------------------


class UserRole(StrEnum):
    SUPERADMIN = "superadmin"
    ORGANIZER = "organizer"
    SCANNER = "scanner"
    CASHIER = "cashier"
    SUPPORT = "support"


user_role_enum = _pg_enum(UserRole, "user_role")


# -------------------- Event --------------------


class EventStatus(StrEnum):
    DRAFT = "draft"
    PENDING_MODERATION = "pending_moderation"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    REJECTED = "rejected"


event_status_enum = _pg_enum(EventStatus, "event_status")


# -------------------- Reservation --------------------


class ReservationStatus(StrEnum):
    DRAFT = "draft"
    PENDING_PAYMENT = "pending_payment"
    PAID = "paid"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


reservation_status_enum = _pg_enum(ReservationStatus, "reservation_status")


# -------------------- Ticket --------------------


class TicketStatus(StrEnum):
    ISSUED = "issued"
    CHECKED_IN = "checked_in"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


ticket_status_enum = _pg_enum(TicketStatus, "ticket_status")


# -------------------- Payment --------------------


class PaymentProviderType(StrEnum):
    QRMANAGER = "qrmanager"
    COMPLIMENTARY = "complimentary"
    CASH = "cash"


payment_provider_enum = _pg_enum(PaymentProviderType, "payment_provider")


class PaymentStatus(StrEnum):
    PENDING = "pending"
    PAID = "paid"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


payment_status_enum = _pg_enum(PaymentStatus, "payment_status")


# -------------------- PromoCode --------------------


class DiscountType(StrEnum):
    PERCENT = "percent"
    FIXED_AMOUNT = "fixed_amount"
    FIXED_PRICE = "fixed_price"


discount_type_enum = _pg_enum(DiscountType, "discount_type")


# -------------------- Billing --------------------


class BalanceTransactionType(StrEnum):
    COMMISSION_DEBIT = "commission_debit"
    TOPUP = "topup"
    MANUAL_ADJUSTMENT = "manual_adjustment"
    REFUND_CREDIT = "refund_credit"


balance_transaction_type_enum = _pg_enum(
    BalanceTransactionType, "balance_transaction_type"
)


# -------------------- Deposit (v1.1) --------------------


class DepositStatus(StrEnum):
    PENDING_PAYMENT = "pending_payment"
    ACTIVE = "active"
    PARTIALLY_USED = "partially_used"
    FULLY_USED = "fully_used"
    EXPIRED = "expired"
    REFUNDED = "refunded"


deposit_status_enum = _pg_enum(DepositStatus, "deposit_status")


class DepositTransactionType(StrEnum):
    CHARGE = "charge"
    REFUND = "refund"
    ADJUSTMENT = "adjustment"


deposit_transaction_type_enum = _pg_enum(
    DepositTransactionType, "deposit_transaction_type"
)
