"""Доменные ошибки для модуля events."""

from __future__ import annotations

from paytools.core.errors import (
    ConflictError,
    DomainError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)


class EventNotFoundError(NotFoundError):
    """Событие не найдено."""

    code = "event_not_found"
    default_message = "Событие не найдено"


class EventSlugTakenError(ConflictError):
    """Slug уже занят в рамках организации."""

    code = "event_slug_taken"
    default_message = "Событие с таким slug уже существует"


class InvalidStatusTransitionError(ConflictError):
    """Недопустимый переход статуса события."""

    code = "invalid_status_transition"
    default_message = "Недопустимый переход статуса"


class CannotPublishError(ForbiddenError):
    """Нельзя опубликовать событие (auto_publish выключен)."""

    code = "cannot_publish"
    default_message = "Публикация невозможна: auto_publish выключен для организации"


class ImageTooLargeError(ValidationError):
    """Изображение превышает максимальный размер."""

    code = "image_too_large"
    default_message = "Изображение превышает максимальный размер 5MB"


class ImageInvalidFormatError(ValidationError):
    """Неподдерживаемый формат изображения."""

    code = "image_invalid_format"
    default_message = "Неподдерживаемый формат изображения. Допустимы: JPEG, PNG, WebP"


class ImageValidationError(ValidationError):
    """Ошибка валидации изображения: MIME, размер, неверный формат.

    Маппится на HTTP 400 — клиент прислал некорректные данные.
    """

    code = "image_validation_error"
    default_message = "Некорректное изображение"


class ImageStorageError(DomainError):
    """Ошибка инфраструктуры: не удалось загрузить изображение в S3.

    Маппится на HTTP 502 — проблема на стороне бэкенда/хранилища,
    клиент не виноват.
    """

    code = "image_storage_error"
    status_code = 502
    default_message = "Не удалось сохранить изображение"


class EventNotEditableError(ConflictError):
    """Событие в статусе, не допускающем редактирование."""

    code = "event_not_editable"
    default_message = "Событие нельзя редактировать в текущем статусе"


class PublishedFieldsRestrictedError(ValidationError):
    """Попытка изменить поля, заблокированные после публикации."""

    code = "published_fields_restricted"
    default_message = "После публикации нельзя менять цены, расписание и тарифы"
