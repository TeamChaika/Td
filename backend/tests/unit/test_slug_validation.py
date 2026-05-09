"""Unit-тесты валидации slug организаций."""

from __future__ import annotations

import pytest

from paytools.domain.organizations.validation import (
    RESERVED_SLUGS,
    SLUG_MAX_LENGTH,
    SlugValidationError,
    is_reserved_slug,
    is_valid_slug,
    validate_slug,
)


class TestValidateSlug:
    """Тесты функции validate_slug."""

    def test_valid_slug_passes(self) -> None:
        """Валидный slug проходит проверку."""
        result = validate_slug("my-org-123")
        assert result == "my-org-123"

    def test_valid_slug_single_word(self) -> None:
        """Slug из одного слова проходит."""
        result = validate_slug("acme")
        assert result == "acme"

    def test_valid_slug_with_numbers(self) -> None:
        """Slug с цифрами проходит."""
        result = validate_slug("event2026")
        assert result == "event2026"

    def test_valid_slug_min_length(self) -> None:
        """Slug минимальной длины (3 символа) проходит."""
        result = validate_slug("abc")
        assert result == "abc"

    def test_valid_slug_max_length(self) -> None:
        """Slug максимальной длины (64 символа) проходит."""
        slug = "a" + "b" * 62 + "c"  # 64 chars
        assert len(slug) == SLUG_MAX_LENGTH
        result = validate_slug(slug)
        assert result == slug

    def test_valid_slug_50_chars(self) -> None:
        """Slug из 50 символов (старый лимит) проходит."""
        slug = "a" + "b" * 48 + "c"  # 50 chars, ранее был лимитом
        result = validate_slug(slug)
        assert result == slug

    def test_too_short_raises(self) -> None:
        """Slug короче 3 символов вызывает ошибку too_short."""
        with pytest.raises(SlugValidationError) as exc_info:
            validate_slug("ab")
        assert exc_info.value.code == "too_short"

    def test_too_short_one_char(self) -> None:
        """Slug из 1 символа вызывает too_short."""
        with pytest.raises(SlugValidationError) as exc_info:
            validate_slug("a")
        assert exc_info.value.code == "too_short"

    def test_too_short_empty(self) -> None:
        """Пустой slug вызывает too_short."""
        with pytest.raises(SlugValidationError) as exc_info:
            validate_slug("")
        assert exc_info.value.code == "too_short"

    def test_too_long_raises(self) -> None:
        """Slug длиннее 64 символов вызывает ошибку too_long."""
        slug = "a" * 65
        with pytest.raises(SlugValidationError) as exc_info:
            validate_slug(slug)
        assert exc_info.value.code == "too_long"

    def test_uppercase_raises_invalid_format(self) -> None:
        """Slug с заглавными буквами вызывает invalid_format."""
        with pytest.raises(SlugValidationError) as exc_info:
            validate_slug("MyOrg")
        assert exc_info.value.code == "invalid_format"

    def test_spaces_raises_invalid_format(self) -> None:
        """Slug с пробелами вызывает invalid_format."""
        with pytest.raises(SlugValidationError) as exc_info:
            validate_slug("my org")
        assert exc_info.value.code == "invalid_format"

    def test_cyrillic_raises_invalid_format(self) -> None:
        """Slug с кириллицей вызывает invalid_format."""
        with pytest.raises(SlugValidationError) as exc_info:
            validate_slug("моя-орг")
        assert exc_info.value.code == "invalid_format"

    def test_special_chars_raises_invalid_format(self) -> None:
        """Slug со спецсимволами вызывает invalid_format."""
        with pytest.raises(SlugValidationError) as exc_info:
            validate_slug("my@org!")
        assert exc_info.value.code == "invalid_format"

    def test_leading_hyphen_raises_invalid_format(self) -> None:
        """Slug с дефисом в начале вызывает invalid_format."""
        with pytest.raises(SlugValidationError) as exc_info:
            validate_slug("-myorg")
        assert exc_info.value.code == "invalid_format"

    def test_trailing_hyphen_raises_invalid_format(self) -> None:
        """Slug с дефисом в конце вызывает invalid_format."""
        with pytest.raises(SlugValidationError) as exc_info:
            validate_slug("myorg-")
        assert exc_info.value.code == "invalid_format"

    def test_double_hyphen_raises_invalid_format(self) -> None:
        """Slug с двойным дефисом вызывает invalid_format."""
        with pytest.raises(SlugValidationError) as exc_info:
            validate_slug("my--org")
        assert exc_info.value.code == "invalid_format"

    def test_underscore_raises_invalid_format(self) -> None:
        """Slug с подчёркиванием вызывает invalid_format."""
        with pytest.raises(SlugValidationError) as exc_info:
            validate_slug("my_org")
        assert exc_info.value.code == "invalid_format"

    def test_reserved_slug_admin_raises(self) -> None:
        """Зарезервированный slug 'admin' вызывает reserved."""
        with pytest.raises(SlugValidationError) as exc_info:
            validate_slug("admin")
        assert exc_info.value.code == "reserved"

    def test_reserved_slug_api_raises(self) -> None:
        """Зарезервированный slug 'api' вызывает reserved."""
        with pytest.raises(SlugValidationError) as exc_info:
            validate_slug("api")
        assert exc_info.value.code == "reserved"

    def test_reserved_slug_platform_raises(self) -> None:
        """Зарезервированный slug 'platform' вызывает reserved."""
        with pytest.raises(SlugValidationError) as exc_info:
            validate_slug("platform")
        assert exc_info.value.code == "reserved"

    def test_reserved_slug_www_raises(self) -> None:
        """Зарезервированный slug 'www' вызывает reserved."""
        with pytest.raises(SlugValidationError) as exc_info:
            validate_slug("www")
        assert exc_info.value.code == "reserved"

    def test_all_reserved_slugs_are_rejected(self) -> None:
        """Все зарезервированные slug-и отклоняются."""
        for slug in RESERVED_SLUGS:
            with pytest.raises(SlugValidationError) as exc_info:
                validate_slug(slug)
            assert exc_info.value.code == "reserved", f"Slug '{slug}' не отклонён"


class TestIsReservedSlug:
    """Тесты функции is_reserved_slug."""

    def test_reserved_returns_true(self) -> None:
        """Зарезервированный slug возвращает True."""
        assert is_reserved_slug("admin") is True
        assert is_reserved_slug("api") is True

    def test_non_reserved_returns_false(self) -> None:
        """Незарезервированный slug возвращает False."""
        assert is_reserved_slug("my-org") is False

    def test_case_insensitive(self) -> None:
        """Проверка регистро-нечувствительная."""
        assert is_reserved_slug("ADMIN") is True
        assert is_reserved_slug("Admin") is True
        assert is_reserved_slug("  admin  ") is True

    def test_empty_string(self) -> None:
        """Пустая строка не зарезервирована."""
        assert is_reserved_slug("") is False


class TestIsValidSlug:
    """Тесты функции is_valid_slug."""

    def test_valid_returns_true(self) -> None:
        """Валидный slug возвращает True."""
        assert is_valid_slug("my-org") is True

    def test_invalid_returns_false(self) -> None:
        """Невалидный slug возвращает False."""
        assert is_valid_slug("ab") is False
        assert is_valid_slug("ADMIN") is False
        assert is_valid_slug("my org") is False
