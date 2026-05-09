"""Валидация Pydantic-схем событий: schedule, capacity_policy, custom_fields.

Импортирует production-схемы из paytools.domain.events.validation.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import pytest
from pydantic import TypeAdapter, ValidationError

from paytools.db.models.enums import EventStatus
from paytools.domain.events.validation import (
    CapacityPolicy,
    CapacityPolicyHybrid,
    CapacityPolicyPerTariff,
    CapacityPolicyTotal,
    CapacityPolicyUnlimited,
    CustomFieldSchema,
    CustomFieldsSchema,
    Schedule,
    SchedulePeriod,
    ScheduleSessions,
    ScheduleSingle,
    SessionItem,
)


# ---------------------------------------------------------------------------
# Тесты: Schedule discriminated union
# ---------------------------------------------------------------------------


class TestScheduleSingle:
    """Тесты single-расписания."""

    def test_valid_single_schedule(self) -> None:
        """Валидное single-расписание парсится без ошибок."""
        data = {
            "type": "single",
            "starts_at": "2026-06-15T18:00:00+03:00",
            "ends_at": "2026-06-15T22:00:00+03:00",
        }
        schedule = ScheduleSingle.model_validate(data)
        assert schedule.type == "single"
        assert schedule.starts_at.year == 2026
        assert schedule.ends_at.hour == 22

    def test_ends_at_must_be_after_starts_at(self) -> None:
        """ends_at должен быть строго позже starts_at."""
        data = {
            "type": "single",
            "starts_at": "2026-06-15T22:00:00+03:00",
            "ends_at": "2026-06-15T18:00:00+03:00",
        }
        adapter = TypeAdapter(Schedule)
        with pytest.raises(ValidationError) as exc:
            adapter.validate_python(data)
        errors = exc.value.errors()
        assert any("должна быть позже" in str(e["msg"]) for e in errors)

    def test_ends_at_equal_to_starts_at_invalid(self) -> None:
        """ends_at == starts_at — невалидно."""
        data = {
            "type": "single",
            "starts_at": "2026-06-15T18:00:00+03:00",
            "ends_at": "2026-06-15T18:00:00+03:00",
        }
        adapter = TypeAdapter(Schedule)
        with pytest.raises(ValidationError) as exc:
            adapter.validate_python(data)
        errors = exc.value.errors()
        assert any("должна быть позже" in str(e["msg"]) for e in errors)

    def test_past_date_invalid(self) -> None:
        """Дата окончания в прошлом — невалидно (AfterValidator)."""
        past = datetime.now(timezone.utc) - timedelta(days=365)
        data = {
            "type": "single",
            "starts_at": past.isoformat(),
            "ends_at": (past + timedelta(hours=4)).isoformat(),
        }
        adapter = TypeAdapter(Schedule)
        with pytest.raises(ValidationError) as exc:
            adapter.validate_python(data)
        errors = exc.value.errors()
        assert any("уже в прошлом" in str(e["msg"]) for e in errors)

    def test_missing_required_fields(self) -> None:
        """Пропуск обязательных полей вызывает ошибку валидации."""
        with pytest.raises(ValidationError):
            ScheduleSingle.model_validate({"type": "single"})


class TestScheduleSessions:
    """Тесты sessions-расписания."""

    def test_valid_sessions_schedule(self) -> None:
        """Валидное sessions-расписание с одним сеансом."""
        data = {
            "type": "sessions",
            "sessions": [
                {
                    "starts_at": "2026-06-15T18:00:00+03:00",
                    "ends_at": "2026-06-15T20:00:00+03:00",
                }
            ],
        }
        schedule = ScheduleSessions.model_validate(data)
        assert schedule.type == "sessions"
        assert len(schedule.sessions) == 1

    def test_multiple_sessions(self) -> None:
        """Несколько сеансов — валидно."""
        data = {
            "type": "sessions",
            "sessions": [
                {
                    "starts_at": "2026-06-15T10:00:00+03:00",
                    "ends_at": "2026-06-15T12:00:00+03:00",
                },
                {
                    "starts_at": "2026-06-15T14:00:00+03:00",
                    "ends_at": "2026-06-15T16:00:00+03:00",
                },
                {
                    "starts_at": "2026-06-15T18:00:00+03:00",
                    "ends_at": "2026-06-15T20:00:00+03:00",
                },
            ],
        }
        schedule = ScheduleSessions.model_validate(data)
        assert len(schedule.sessions) == 3

    def test_empty_sessions_invalid(self) -> None:
        """Пустой список сеансов — невалидно (min_length=1)."""
        data = {"type": "sessions", "sessions": []}
        with pytest.raises(ValidationError):
            ScheduleSessions.model_validate(data)

    def test_session_ends_before_starts_invalid(self) -> None:
        """Сеанс с ends_at < starts_at — невалидно."""
        data = {
            "type": "sessions",
            "sessions": [
                {
                    "starts_at": "2026-06-15T20:00:00+03:00",
                    "ends_at": "2026-06-15T18:00:00+03:00",
                }
            ],
        }
        adapter = TypeAdapter(Schedule)
        with pytest.raises(ValidationError) as exc:
            adapter.validate_python(data)
        errors = exc.value.errors()
        assert any("должна быть позже" in str(e["msg"]) for e in errors)

    def test_session_auto_generates_id(self) -> None:
        """Если id не передан — генерируется автоматически."""
        data = {
            "type": "sessions",
            "sessions": [
                {
                    "starts_at": "2026-06-15T18:00:00+03:00",
                    "ends_at": "2026-06-15T20:00:00+03:00",
                }
            ],
        }
        schedule = ScheduleSessions.model_validate(data)
        assert isinstance(schedule.sessions[0].id, UUID)

    def test_overlapping_sessions_invalid(self) -> None:
        """Пересекающиеся сеансы — невалидно."""
        data = {
            "type": "sessions",
            "sessions": [
                {
                    "starts_at": "2026-06-15T10:00:00+03:00",
                    "ends_at": "2026-06-15T14:00:00+03:00",
                },
                {
                    "starts_at": "2026-06-15T12:00:00+03:00",
                    "ends_at": "2026-06-15T16:00:00+03:00",
                },
            ],
        }
        adapter = TypeAdapter(Schedule)
        with pytest.raises(ValidationError) as exc:
            adapter.validate_python(data)
        errors = exc.value.errors()
        assert any("начинается раньше окончания предыдущего" in str(e["msg"]) for e in errors)


class TestSchedulePeriod:
    """Тесты period-расписания."""

    def test_valid_period_schedule(self) -> None:
        """Валидное period-расписание."""
        data = {
            "type": "period",
            "starts_at": "2026-07-01T00:00:00+03:00",
            "ends_at": "2026-07-05T23:59:59+03:00",
        }
        schedule = SchedulePeriod.model_validate(data)
        assert schedule.type == "period"

    def test_period_ends_before_starts_invalid(self) -> None:
        """Период с ends_at < starts_at — невалидно."""
        data = {
            "type": "period",
            "starts_at": "2026-07-05T00:00:00+03:00",
            "ends_at": "2026-07-01T00:00:00+03:00",
        }
        adapter = TypeAdapter(Schedule)
        with pytest.raises(ValidationError) as exc:
            adapter.validate_python(data)
        errors = exc.value.errors()
        assert any("должна быть позже" in str(e["msg"]) for e in errors)


class TestScheduleDiscriminatedUnion:
    """Тесты discriminated union — парсинг по полю type."""

    def test_parses_single(self) -> None:
        """Парсит single по type=single."""
        data = {
            "type": "single",
            "starts_at": "2026-06-15T18:00:00+03:00",
            "ends_at": "2026-06-15T22:00:00+03:00",
        }
        adapter = TypeAdapter(Schedule)
        result = adapter.validate_python(data)
        assert isinstance(result, ScheduleSingle)

    def test_parses_sessions(self) -> None:
        """Парсит sessions по type=sessions."""
        data = {
            "type": "sessions",
            "sessions": [
                {
                    "starts_at": "2026-06-15T18:00:00+03:00",
                    "ends_at": "2026-06-15T20:00:00+03:00",
                }
            ],
        }
        adapter = TypeAdapter(Schedule)
        result = adapter.validate_python(data)
        assert isinstance(result, ScheduleSessions)

    def test_parses_period(self) -> None:
        """Парсит period по type=period."""
        data = {
            "type": "period",
            "starts_at": "2026-07-01T00:00:00+03:00",
            "ends_at": "2026-07-05T23:59:59+03:00",
        }
        adapter = TypeAdapter(Schedule)
        result = adapter.validate_python(data)
        assert isinstance(result, SchedulePeriod)

    def test_unknown_type_invalid(self) -> None:
        """Неизвестный type вызывает ошибку."""
        data = {
            "type": "unknown_type",
            "starts_at": "2026-06-15T18:00:00+03:00",
            "ends_at": "2026-06-15T22:00:00+03:00",
        }
        adapter = TypeAdapter(Schedule)
        with pytest.raises(ValidationError):
            adapter.validate_python(data)

    def test_missing_type_invalid(self) -> None:
        """Отсутствие поля type вызывает ошибку."""
        data = {
            "starts_at": "2026-06-15T18:00:00+03:00",
            "ends_at": "2026-06-15T22:00:00+03:00",
        }
        adapter = TypeAdapter(Schedule)
        with pytest.raises(ValidationError):
            adapter.validate_python(data)


# ---------------------------------------------------------------------------
# Тесты: CapacityPolicy discriminated union
# ---------------------------------------------------------------------------


class TestCapacityPolicyTotal:
    """Тесты total capacity policy."""

    def test_valid_total(self) -> None:
        """Валидный total-лимит."""
        policy = CapacityPolicyTotal.model_validate({"type": "total", "limit": 200})
        assert policy.type == "total"
        assert policy.limit == 200

    def test_limit_zero_invalid(self) -> None:
        """limit=0 — невалидно (gt=0 в production-схеме)."""
        with pytest.raises(ValidationError):
            CapacityPolicyTotal.model_validate({"type": "total", "limit": 0})

    def test_limit_negative_invalid(self) -> None:
        """Отрицательный limit — невалидно."""
        with pytest.raises(ValidationError):
            CapacityPolicyTotal.model_validate({"type": "total", "limit": -1})


class TestCapacityPolicyPerTariff:
    """Тесты per_tariff capacity policy."""

    def test_valid_per_tariff(self) -> None:
        """Валидный per_tariff (без дополнительных полей)."""
        policy = CapacityPolicyPerTariff.model_validate({"type": "per_tariff"})
        assert policy.type == "per_tariff"


class TestCapacityPolicyHybrid:
    """Тесты hybrid capacity policy."""

    def test_valid_hybrid(self) -> None:
        """Валидный hybrid с общим лимитом."""
        policy = CapacityPolicyHybrid.model_validate({"type": "hybrid", "total": 200})
        assert policy.type == "hybrid"
        assert policy.total == 200


class TestCapacityPolicyUnlimited:
    """Тесты unlimited capacity policy."""

    def test_valid_unlimited(self) -> None:
        """Валидный unlimited (без дополнительных полей)."""
        policy = CapacityPolicyUnlimited.model_validate({"type": "unlimited"})
        assert policy.type == "unlimited"


class TestCapacityPolicyDiscriminatedUnion:
    """Тесты discriminated union для capacity_policy."""

    def test_parses_total(self) -> None:
        """Парсит total по type=total."""
        adapter = TypeAdapter(CapacityPolicy)
        result = adapter.validate_python({"type": "total", "limit": 100})
        assert isinstance(result, CapacityPolicyTotal)

    def test_parses_per_tariff(self) -> None:
        """Парсит per_tariff."""
        adapter = TypeAdapter(CapacityPolicy)
        result = adapter.validate_python({"type": "per_tariff"})
        assert isinstance(result, CapacityPolicyPerTariff)

    def test_parses_hybrid(self) -> None:
        """Парсит hybrid."""
        adapter = TypeAdapter(CapacityPolicy)
        result = adapter.validate_python({"type": "hybrid", "total": 50})
        assert isinstance(result, CapacityPolicyHybrid)

    def test_parses_unlimited(self) -> None:
        """Парсит unlimited."""
        adapter = TypeAdapter(CapacityPolicy)
        result = adapter.validate_python({"type": "unlimited"})
        assert isinstance(result, CapacityPolicyUnlimited)


# ---------------------------------------------------------------------------
# Тесты: CustomFieldsSchema
# ---------------------------------------------------------------------------


class TestCustomFieldSchema:
    """Тесты валидации одного кастомного поля."""

    def test_valid_text_field(self) -> None:
        """Валидное текстовое поле."""
        field = CustomFieldSchema.model_validate(
            {"id": "comment", "label": "Комментарий", "type": "text", "required": False}
        )
        assert field.id == "comment"
        assert field.type == "text"

    def test_valid_select_with_options(self) -> None:
        """select с options — валидно."""
        field = CustomFieldSchema.model_validate(
            {
                "id": "diet",
                "label": "Диета",
                "type": "select",
                "options": ["нет", "веган", "вегетарианец"],
                "required": False,
            }
        )
        assert field.options == ["нет", "веган", "вегетарианец"]

    def test_select_without_options_parsed_at_field_level(self) -> None:
        """select без options парсится на уровне поля (проверка в списке)."""
        field = CustomFieldSchema.model_validate(
            {"id": "diet", "label": "Диета", "type": "select", "required": False}
        )
        assert field.options is None

    def test_unsupported_type_invalid(self) -> None:
        """Неподдерживаемый тип поля — невалидно (Literal)."""
        with pytest.raises(ValidationError):
            CustomFieldSchema.model_validate(
                {
                    "id": "bad",
                    "label": "Bad Field",
                    "type": "unsupported_type",
                    "required": False,
                }
            )

    def test_all_supported_types(self) -> None:
        """Все типы из Literal валидны."""
        supported = [
            "text", "textarea", "number", "select",
            "multiselect", "checkbox", "date",
        ]
        for field_type in supported:
            data: dict[str, Any] = {
                "id": f"field_{field_type}",
                "label": f"Field {field_type}",
                "type": field_type,
                "required": False,
            }
            if field_type in ("select", "multiselect"):
                data["options"] = ["option1", "option2"]
            field = CustomFieldSchema.model_validate(data)
            assert field.type == field_type

    def test_empty_id_invalid(self) -> None:
        """Пустой id — невалидно."""
        with pytest.raises(ValidationError):
            CustomFieldSchema.model_validate(
                {"id": "", "label": "Test", "type": "text", "required": False}
            )

    def test_empty_label_invalid(self) -> None:
        """Пустой label — невалидно."""
        with pytest.raises(ValidationError):
            CustomFieldSchema.model_validate(
                {"id": "test", "label": "", "type": "text", "required": False}
            )

    def test_id_pattern_latin_only(self) -> None:
        """id должен соответствовать паттерну ^[a-z0-9_]+$."""
        with pytest.raises(ValidationError):
            CustomFieldSchema.model_validate(
                {
                    "id": "русский_id",
                    "label": "Test",
                    "type": "text",
                    "required": False,
                }
            )


class TestCustomFieldsSchemaList:
    """Тесты списка кастомных полей (ограничения)."""

    def test_max_10_fields(self) -> None:
        """Максимум 10 полей в custom_fields_schema."""
        fields = [
            CustomFieldSchema(
                id=f"field_{i}", label=f"Field {i}", type="text", required=False
            )
            for i in range(11)
        ]
        with pytest.raises(ValidationError) as exc:
            TypeAdapter(CustomFieldsSchema).validate_python(fields)
        errors = exc.value.errors()
        assert any("Не более 10" in str(e["msg"]) for e in errors)

    def test_unique_ids_required(self) -> None:
        """ID полей должны быть уникальны."""
        fields = [
            CustomFieldSchema(
                id="same_id", label="Field 1", type="text", required=False
            ),
            CustomFieldSchema(
                id="same_id", label="Field 2", type="text", required=False
            ),
        ]
        with pytest.raises(ValidationError) as exc:
            TypeAdapter(CustomFieldsSchema).validate_python(fields)
        errors = exc.value.errors()
        assert any("уникальными" in str(e["msg"]) for e in errors)

    def test_select_without_options_in_list_invalid(self) -> None:
        """select без options в списке — невалидно."""
        fields = [
            CustomFieldSchema(
                id="diet", label="Диета", type="select", required=False
            ),
        ]
        with pytest.raises(ValidationError) as exc:
            TypeAdapter(CustomFieldsSchema).validate_python(fields)
        errors = exc.value.errors()
        assert any("options" in str(e["msg"]).lower() for e in errors)

    def test_none_is_valid(self) -> None:
        """None — валидное значение для CustomFieldsSchema."""
        result = TypeAdapter(CustomFieldsSchema).validate_python(None)
        assert result is None

    def test_empty_list_is_valid(self) -> None:
        """Пустой список — валидно."""
        result = TypeAdapter(CustomFieldsSchema).validate_python([])
        assert result == []

    def test_10_fields_is_valid(self) -> None:
        """Ровно 10 полей — валидно."""
        fields = [
            CustomFieldSchema(
                id=f"field_{i}", label=f"Field {i}", type="text", required=False
            )
            for i in range(10)
        ]
        result = TypeAdapter(CustomFieldsSchema).validate_python(fields)
        assert len(result) == 10


# ---------------------------------------------------------------------------
# Тесты: EventStatus enum
# ---------------------------------------------------------------------------


class TestEventStatusEnum:
    """Тесты перечисления статусов события."""

    def test_all_statuses_present(self) -> None:
        """Все ожидаемые статусы присутствуют."""
        expected = {"draft", "pending_moderation", "published", "archived", "rejected"}
        actual = {s.value for s in EventStatus}
        assert actual == expected

    def test_default_is_draft(self) -> None:
        """Статус по умолчанию — draft."""
        assert EventStatus.DRAFT.value == "draft"