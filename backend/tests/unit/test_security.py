from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from paytools.core.config import get_settings
from paytools.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    decrypt_secret,
    encrypt_secret,
    generate_token,
    hash_password,
    hmac_sign,
    hmac_verify,
    verify_password,
)


class TestPasswords:
    def test_hash_password_returns_bcrypt_string(self):
        """Хэш выглядит как bcrypt и отличается для одного и того же пароля."""
        h1 = hash_password("MyStrong!Pass123")
        h2 = hash_password("MyStrong!Pass123")
        assert h1.startswith("$2b$")  # bcrypt
        assert h1 != h2  # разные соли

    def test_verify_password_correct(self):
        pw = "secret123456"
        assert verify_password(pw, hash_password(pw))

    def test_verify_password_wrong(self):
        assert not verify_password("wrong", hash_password("right"))

    def test_verify_password_does_not_raise_on_garbage_hash(self):
        """Некорректный хэш не вызывает исключение, а возвращает False."""
        assert verify_password("any", "not-a-valid-hash") is False
        assert verify_password("any", "") is False

    def test_hash_password_on_unicode(self):
        """Unicode-пароли (кириллица, эмодзи) работают."""
        pw = "парольПароль123🔐"
        assert verify_password(pw, hash_password(pw))


class TestJWT:
    def test_create_and_decode_access_token(self):
        token = create_access_token({"sub": "user-123", "role": "organizer"})
        decoded = decode_token(token)
        assert decoded["sub"] == "user-123"
        assert decoded["role"] == "organizer"
        assert decoded["type"] == "access"
        assert "exp" in decoded
        assert "iat" in decoded
        assert "jti" in decoded

    def test_create_refresh_token_has_type_refresh(self):
        token = create_refresh_token({"sub": "user-123"})
        decoded = decode_token(token)
        assert decoded["type"] == "refresh"

    def test_two_tokens_have_different_jti(self):
        t1 = create_access_token({"sub": "x"})
        t2 = create_access_token({"sub": "x"})
        assert decode_token(t1)["jti"] != decode_token(t2)["jti"]

    def test_decode_invalid_signature(self):
        """Подделанный токен не декодируется."""
        good = create_access_token({"sub": "x"})
        # Ломаем последний символ подписи
        bad = good[:-1] + ("A" if good[-1] != "A" else "B")
        with pytest.raises(jwt.InvalidTokenError):
            decode_token(bad)

    def test_decode_expired_token(self):
        """Истёкший токен бросает InvalidTokenError."""
        settings = get_settings()
        expired = jwt.encode(
            {
                "sub": "x",
                "exp": int((datetime.now(UTC) - timedelta(hours=1)).timestamp()),
                "type": "access",
            },
            settings.jwt_secret,
            algorithm="HS256",
        )
        with pytest.raises(jwt.ExpiredSignatureError):
            decode_token(expired)


class TestHmac:
    def test_sign_and_verify(self):
        sig = hmac_sign("payload", "secret")
        assert hmac_verify("payload", sig, "secret")

    def test_verify_wrong_signature(self):
        assert not hmac_verify("payload", "deadbeef", "secret")

    def test_verify_wrong_secret(self):
        sig = hmac_sign("payload", "secret1")
        assert not hmac_verify("payload", sig, "secret2")

    def test_sign_bytes_and_str_consistent(self):
        """Подпись одинакова для str и bytes с тем же содержимым."""
        s1 = hmac_sign("hello", "k")
        s2 = hmac_sign(b"hello", "k")
        assert s1 == s2

    def test_signature_is_hex(self):
        sig = hmac_sign("x", "k")
        int(sig, 16)  # не должно падать
        assert len(sig) == 64  # sha256 hex


class TestEncryption:
    def test_roundtrip(self):
        secret = "sk_live_qrm_abc123"
        encrypted = encrypt_secret(secret)
        assert encrypted != secret
        assert decrypt_secret(encrypted) == secret

    def test_empty_string(self):
        assert encrypt_secret("") == ""
        assert decrypt_secret("") == ""

    def test_decrypt_invalid_raises(self):
        with pytest.raises(ValueError):
            decrypt_secret("not-encrypted-at-all")

    def test_two_encryptions_differ(self):
        """Fernet добавляет nonce, одинаковый plaintext → разный ciphertext."""
        e1 = encrypt_secret("same")
        e2 = encrypt_secret("same")
        assert e1 != e2
        assert decrypt_secret(e1) == decrypt_secret(e2) == "same"

    def test_unicode_secret(self):
        secret = "токен-с-emoji-🔑"
        assert decrypt_secret(encrypt_secret(secret)) == secret


class TestGenerateToken:
    def test_default_length_is_urlsafe(self):
        tok = generate_token()
        # URL-safe base64, минимум 32 байта → минимум 43 символа
        assert len(tok) >= 43
        # Только url-safe символы
        import string

        allowed = set(string.ascii_letters + string.digits + "-_")
        assert set(tok) <= allowed

    def test_uniqueness(self):
        tokens = {generate_token() for _ in range(100)}
        assert len(tokens) == 100  # все разные
