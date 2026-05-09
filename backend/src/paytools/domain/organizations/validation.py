"""Валидация slug для организаций.

Slug — это человекочитаемый идентификатор организации, используемый в URL
(например, https://app.paytools.ru/org/my-cool-company). Жёсткие правила валидации
нужны, чтобы гарантировать уникальность, избежать коллизий с системными маршрутами
и обеспечить единообразный внешний вид.
"""

import re

# --------------------------------------------------------------------------- #
# Константы
# --------------------------------------------------------------------------- #

SLUG_MIN_LENGTH: int = 3
"""Минимальная допустимая длина slug."""

SLUG_MAX_LENGTH: int = 64
"""Максимальная допустимая длина slug (ограничение колонки в БД)."""

SLUG_PATTERN: re.Pattern[str] = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
"""
Скомпилированный паттерн для валидации slug.

Разрешены:
- Строчные латинские буквы (a-z) и цифры (0-9)
- Дефисы только между буквенно-цифровыми сегментами
- Не допускается: дефис в начале/конце, подряд идущие дефисы, пустая строка
"""

RESERVED_SLUGS: frozenset[str] = frozenset(
    {
        "www",
        "admin",
        "api",
        "platform",
        "scanner",
        "app",
        "mail",
        "support",
        "help",
        "docs",
        "blog",
        "static",
        "assets",
        "cdn",
    }
)
"""
Slug-и, запрещённые к использованию организациями.

Зарезервированы, чтобы избежать коллизий:
- С системными маршрутами платформы (admin, api, platform, scanner, app)
- С общепринятыми поддоменами инфраструктуры (www, mail, static, assets, cdn)
- С будущими публичными разделами платформы (support, help, docs, blog)
"""

# --------------------------------------------------------------------------- #
# Исключения
# --------------------------------------------------------------------------- #


class SlugValidationError(ValueError):
    """Ошибка валидации slug.

    Атрибут ``code`` содержит машинночитаемый код ошибки, чтобы клиенты API
    могли программно различать причины отклонения slug без парсинга сообщения.

    Допустимые коды:
    - ``"too_short"`` — slug короче минимальной длины
    - ``"too_long"`` — slug длиннее максимальной длины
    - ``"invalid_format"`` — slug не соответствует шаблону (латиница, цифры, дефисы)
    - ``"reserved"`` — slug входит в список зарезервированных
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


# --------------------------------------------------------------------------- #
# Публичные функции
# --------------------------------------------------------------------------- #


def validate_slug(slug: str) -> str:
    """Провалидировать slug организации.

    Выполняет последовательные проверки:
    1. Длина меньше минимальной — ошибка ``too_short``.
    2. Длина больше максимальной — ошибка ``too_long``.
    3. Несоответствие шаблону — ошибка ``invalid_format``.
    4. Slug зарезервирован — ошибка ``reserved``.

    Args:
        slug: Сырой входной slug для проверки.

    Returns:
        Исходный slug без изменений, если он корректен.

    Raises:
        SlugValidationError: Если slug не проходит любую из проверок.
    """
    length = len(slug)

    if length < SLUG_MIN_LENGTH:
        raise SlugValidationError(
            code="too_short",
            message=(
                f"Slug must be at least {SLUG_MIN_LENGTH} characters, got {length}"
            ),
        )

    if length > SLUG_MAX_LENGTH:
        raise SlugValidationError(
            code="too_long",
            message=(
                f"Slug must be at most {SLUG_MAX_LENGTH} characters, got {length}"
            ),
        )

    if not SLUG_PATTERN.match(slug):
        raise SlugValidationError(
            code="invalid_format",
            message=(
                "Slug must contain only lowercase letters (a-z), digits (0-9), "
                "and single hyphens between alphanumeric segments "
                "(e.g. 'my-org-123')"
            ),
        )

    if is_reserved_slug(slug):
        raise SlugValidationError(
            code="reserved",
            message=f"Slug '{slug}' is reserved and cannot be used",
        )

    return slug


def is_reserved_slug(slug: str) -> bool:
    """Проверить, что slug входит в зарезервированный список.

    Перед проверкой slug нормализуется: приводится к нижнему регистру
    и очищается от ведущих/завершающих пробелов.  Это гарантирует, что
    вариации вроде ``" Admin "`` или ``"ADMIN"`` тоже будут отклонены.

    Args:
        slug: Строка для проверки.

    Returns:
        ``True`` если slug зарезервирован, ``False`` иначе.
    """
    return slug.strip().lower() in RESERVED_SLUGS


def is_valid_slug(slug: str) -> bool:
    """Проверить, является ли slug валидным, без проброса исключения.

    Удобная обёртка для случаев, когда нужно просто да/нет —
    например, в валидаторах Pydantic или формах на фронтенде.

    Args:
        slug: Строка для проверки.

    Returns:
        ``True`` если slug корректен, ``False`` иначе.
    """
    try:
        validate_slug(slug)
    except SlugValidationError:
        return False
    return True
