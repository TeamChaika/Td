"""Генерация slug для событий из title."""

from __future__ import annotations

from slugify import slugify as _slugify


def slugify(title: str) -> str:
    """Преобразовать title в slug: транслитерация, lowercase, замена пробелов на дефисы.

    Использует python-slugify для корректной транслитерации кириллицы.
    Обрезает до 128 символов (максимальная длина slug в БД).
    """
    slug = _slugify(
        title,
        max_length=128,
        word_boundary=True,
        separator="-",
        lowercase=True,
    )

    # Если после всех преобразований пусто — fallback
    if not slug:
        slug = "event"

    return slug


def make_unique_slug(base_slug: str, attempt: int) -> str:
    """Добавить суффикс к slug для уникальности.

    Пример: 'my-event' → 'my-event-2', 'my-event-3', ...
    """
    suffix = f"-{attempt}"
    # Учитываем, что slug не должен превышать 128 символов
    max_base = 128 - len(suffix)
    return base_slug[:max_base] + suffix
