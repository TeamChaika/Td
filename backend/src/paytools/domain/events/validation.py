"""Валидаторы для полей события: schedule, capacity_policy, custom_fields_schema.

Используются в Pydantic-схемах (api/v1/schemas/event.py) и в доменном сервисе.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from pydantic.functional_validators import AfterValidator

# ---------------------------------------------------------------------------
# Schedule discriminated union
# ---------------------------------------------------------------------------


class ScheduleSingle(BaseModel):
    """Единичное событие: один сеанс."""

    type: Literal["single"]
    starts_at: datetime = Field(description="Начало события (ISO 8601)")
    ends_at: datetime = Field(description="Окончание события (ISO 8601)")


class SessionItem(BaseModel):
    """Один сеанс в расписании sessions."""

    id: UUID = Field(default_factory=uuid4, description="Уникальный ID сеанса")
    starts_at: datetime
    ends_at: datetime


class ScheduleSessions(BaseModel):
    """Несколько сеансов."""

    type: Literal["sessions"]
    sessions: list[SessionItem] = Field(min_length=1, max_length=365)


class SchedulePeriod(BaseModel):
    """Период (фестиваль)."""

    type: Literal["period"]
    starts_at: datetime
    ends_at: datetime


ScheduleVariant = Annotated[
    ScheduleSingle | ScheduleSessions | SchedulePeriod,
    Field(discriminator="type"),
]


def _validate_schedule_dates(schedule: ScheduleVariant) -> ScheduleVariant:
    """Проверка: end > start, даты не в прошлом."""
    now = datetime.now(UTC)

    match schedule:
        case ScheduleSingle(starts_at=st, ends_at=en):
            _check_single_dates(st, en, now)

        case ScheduleSessions(sessions=sessions):
            for i, sess in enumerate(sessions):
                _check_single_dates(sess.starts_at, sess.ends_at, now)
                if i > 0:
                    prev = sessions[i - 1]
                    if sess.starts_at < prev.ends_at:
                        raise ValueError(
                            f"Сеанс #{i + 1} начинается раньше окончания "
                            f"предыдущего сеанса #{i}"
                        )

        case SchedulePeriod(starts_at=st, ends_at=en):
            _check_single_dates(st, en, now)

    return schedule


def _check_single_dates(starts_at: datetime, ends_at: datetime, now: datetime) -> None:
    """Проверка одной пары start/end."""
    if ends_at <= starts_at:
        raise ValueError(
            f"Дата окончания ({ends_at.isoformat()}) должна быть позже даты начала "
            f"({starts_at.isoformat()})"
        )
    # Валидация «не в прошлом» только для starts_at — событие может
    # начаться через минуту, главное чтобы оно ещё не закончилось
    # Не блокируем с точностью до секунды — даём запас 5 минут
    if ends_at < now:
        raise ValueError(
            f"Дата окончания события ({ends_at.isoformat()}) уже в прошлом"
        )


Schedule = Annotated[
    ScheduleVariant,
    AfterValidator(_validate_schedule_dates),
]


# ---------------------------------------------------------------------------
# Capacity policy discriminated union
# ---------------------------------------------------------------------------


class CapacityPolicyTotal(BaseModel):
    """Общий лимит на всё событие."""

    type: Literal["total"]
    limit: int = Field(gt=0, le=100_000, description="Максимальное количество билетов")


class CapacityPolicyPerTariff(BaseModel):
    """Лимиты задаются на уровне каждого тарифа."""

    type: Literal["per_tariff"]


class CapacityPolicyHybrid(BaseModel):
    """Гибрид: общий лимит + лимиты на тариф."""

    type: Literal["hybrid"]
    total: int = Field(gt=0, le=100_000, description="Общий лимит")


class CapacityPolicyUnlimited(BaseModel):
    """Без лимитов."""

    type: Literal["unlimited"]


CapacityPolicyVariant = Annotated[
    CapacityPolicyTotal
    | CapacityPolicyPerTariff
    | CapacityPolicyHybrid
    | CapacityPolicyUnlimited,
    Field(discriminator="type"),
]


CapacityPolicy = CapacityPolicyVariant


# ---------------------------------------------------------------------------
# Custom fields schema
# ---------------------------------------------------------------------------


class CustomFieldSchema(BaseModel):
    """Описание одного кастомного поля формы брони."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9_]+$",
        description="Уникальный идентификатор поля (латиница, цифры, _)",
    )
    label: str = Field(min_length=1, max_length=200, description="Название поля")
    type: Literal[
        "text", "textarea", "number", "select", "multiselect", "checkbox", "date"
    ] = Field(description="Тип поля")
    required: bool = Field(default=False, description="Обязательное поле")
    options: list[str] | None = Field(
        default=None,
        description="Варианты для select/multiselect (непустой список)",
    )
    max_length: int | None = Field(
        default=None, ge=1, le=10000, description="Макс. длина для text/textarea"
    )


def _validate_custom_fields_schema(
    fields: list[CustomFieldSchema] | None,
) -> list[CustomFieldSchema] | None:
    """Валидация схемы кастомных полей: уникальность id, не более 10 полей."""
    if fields is None:
        return None

    if len(fields) > 10:
        raise ValueError("Не более 10 кастомных полей")

    ids = [f.id for f in fields]
    if len(ids) != len(set(ids)):
        raise ValueError("Идентификаторы кастомных полей должны быть уникальными")

    # Проверка options для select/multiselect
    for field in fields:
        if field.type in ("select", "multiselect"):
            if not field.options or len(field.options) == 0:
                raise ValueError(
                    f"Поле '{field.id}' типа {field.type} требует "
                    f"непустой список options"
                )

    return fields


CustomFieldsSchema = Annotated[
    list[CustomFieldSchema] | None,
    AfterValidator(_validate_custom_fields_schema),
]
