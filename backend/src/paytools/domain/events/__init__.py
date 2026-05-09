"""Доменный модуль управления событиями."""

from paytools.domain.events.errors import (
    CannotPublishError,
    EventNotEditableError,
    EventNotFoundError,
    EventSlugTakenError,
    ImageInvalidFormatError,
    ImageStorageError,
    ImageTooLargeError,
    ImageValidationError,
    InvalidStatusTransitionError,
    PublishedFieldsRestrictedError,
)
from paytools.domain.events.service import (
    CreateEventInput,
    EventService,
    UpdateEventInput,
)
from paytools.domain.events.slug import slugify
from paytools.domain.events.validation import (
    CapacityPolicy,
    CustomFieldSchema,
    CustomFieldsSchema,
    Schedule,
    SchedulePeriod,
    ScheduleSessions,
    ScheduleSingle,
)

__all__ = [
    "CannotPublishError",
    "CapacityPolicy",
    "CreateEventInput",
    "CustomFieldSchema",
    "CustomFieldsSchema",
    "EventNotEditableError",
    "EventNotFoundError",
    "EventService",
    "EventSlugTakenError",
    "ImageInvalidFormatError",
    "ImageStorageError",
    "ImageTooLargeError",
    "ImageValidationError",
    "InvalidStatusTransitionError",
    "PublishedFieldsRestrictedError",
    "Schedule",
    "SchedulePeriod",
    "ScheduleSessions",
    "ScheduleSingle",
    "UpdateEventInput",
    "slugify",
]
