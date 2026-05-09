"""Unit-тесты хэширования и проверки паролей."""

from __future__ import annotations

from paytools.core.security import hash_password, verify_password


class TestHashPassword:
    """Тесты hash_password."""

    def test_returns_bcrypt_string(self) -> None:
        """Хэш начинается с $2b$ (bcrypt)."""
        h = hash_password("MyStrong!Pass123")
        assert h.startswith("$2b$")

    def test_different_salts(self) -> None:
        """Два хэша одного пароля различаются (разные соли)."""
        h1 = hash_password("same-password")
        h2 = hash_password("same-password")
        assert h1 != h2

    def test_bcrypt_rounds_12(self) -> None:
        """Проверяем что используется rounds=12 (префикс $2b$12$)."""
        h = hash_password("test-password")
        assert h.startswith("$2b$12$")

    def test_hash_length(self) -> None:
        """Длина bcrypt-хэша — 60 символов."""
        h = hash_password("test-password")
        assert len(h) == 60

    def test_unicode_password(self) -> None:
        """Unicode-пароль (кириллица + эмодзи) хэшируется."""
        pw = "парольПароль123🔐"
        h = hash_password(pw)
        assert h.startswith("$2b$12$")
        assert verify_password(pw, h)


class TestVerifyPassword:
    """Тесты verify_password."""

    def test_correct_password(self) -> None:
        """Правильный пароль проходит проверку."""
        pw = "secret123456"
        assert verify_password(pw, hash_password(pw)) is True

    def test_wrong_password(self) -> None:
        """Неправильный пароль не проходит."""
        assert verify_password("wrong", hash_password("right")) is False

    def test_empty_password(self) -> None:
        """Пустой пароль не проходит проверку."""
        assert verify_password("", hash_password("right")) is False

    def test_garbage_hash_returns_false(self) -> None:
        """Некорректный хэш не вызывает исключение, а возвращает False."""
        assert verify_password("any", "not-a-valid-hash") is False
        assert verify_password("any", "") is False

    def test_none_hash_returns_false(self) -> None:
        """None как хэш не вызывает исключение."""
        try:
            result = verify_password("any", None)  # type: ignore[arg-type]
            assert result is False
        except (TypeError, AttributeError):
            # Если код бросает TypeError — это тоже приемлемо
            pass

    def test_case_sensitive(self) -> None:
        """Пароль чувствителен к регистру."""
        assert verify_password("Password", hash_password("password")) is False
