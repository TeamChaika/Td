"""Unit-тесты JWT-токенов: создание, декодирование, edge cases."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from paytools.core.config import get_settings
from paytools.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
)


class TestCreateAccessToken:
    """Тесты create_access_token."""

    def test_creates_valid_token(self) -> None:
        """Создаёт валидный JWT, который декодируется."""
        token = create_access_token({"sub": "user-123", "role": "organizer"})
        decoded = decode_token(token)
        assert decoded["sub"] == "user-123"
        assert decoded["role"] == "organizer"

    def test_has_type_access(self) -> None:
        """Токен имеет type=access."""
        token = create_access_token({"sub": "x"})
        decoded = decode_token(token)
        assert decoded["type"] == "access"

    def test_has_required_claims(self) -> None:
        """Токен содержит все обязательные claims."""
        token = create_access_token(
            {"sub": "user-1", "org": "org-1", "role": "organizer"}
        )
        decoded = decode_token(token)
        assert "sub" in decoded
        assert "org" in decoded
        assert "role" in decoded
        assert "type" in decoded
        assert "exp" in decoded
        assert "iat" in decoded
        assert "jti" in decoded

    def test_jti_is_unique(self) -> None:
        """Два токена имеют разные jti."""
        t1 = create_access_token({"sub": "x"})
        t2 = create_access_token({"sub": "x"})
        assert decode_token(t1)["jti"] != decode_token(t2)["jti"]

    def test_jti_is_uuid_format(self) -> None:
        """jti имеет формат UUID."""
        token = create_access_token({"sub": "x"})
        jti = decode_token(token)["jti"]
        # UUID v4: 36 символов с дефисами
        assert len(jti) == 36
        assert jti.count("-") == 4

    def test_exp_is_future(self) -> None:
        """exp в будущем (токен не истёк)."""
        token = create_access_token({"sub": "x"})
        decoded = decode_token(token)
        now_ts = int(datetime.now(UTC).timestamp())
        assert decoded["exp"] > now_ts

    def test_iat_is_recent(self) -> None:
        """iat близок к текущему времени."""
        token = create_access_token({"sub": "x"})
        decoded = decode_token(token)
        now_ts = int(datetime.now(UTC).timestamp())
        assert abs(decoded["iat"] - now_ts) < 5  # в пределах 5 секунд


class TestCreateRefreshToken:
    """Тесты create_refresh_token."""

    def test_has_type_refresh(self) -> None:
        """Refresh-токен имеет type=refresh."""
        token = create_refresh_token({"sub": "user-123"})
        decoded = decode_token(token)
        assert decoded["type"] == "refresh"

    def test_longer_ttl_than_access(self) -> None:
        """Refresh-токен живёт дольше access-токена."""
        access = create_access_token({"sub": "x"})
        refresh = create_refresh_token({"sub": "x"})
        access_exp = decode_token(access)["exp"]
        refresh_exp = decode_token(refresh)["exp"]
        assert refresh_exp > access_exp


class TestDecodeToken:
    """Тесты decode_token."""

    def test_valid_token_decodes(self) -> None:
        """Валидный токен декодируется без ошибок."""
        token = create_access_token({"sub": "user-1"})
        decoded = decode_token(token)
        assert decoded["sub"] == "user-1"

    def test_invalid_signature_raises(self) -> None:
        """Токен с неверной подписью вызывает InvalidTokenError."""
        good = create_access_token({"sub": "x"})
        # Ломаем последний символ подписи
        bad = good[:-1] + ("A" if good[-1] != "A" else "B")
        with pytest.raises(jwt.InvalidTokenError):
            decode_token(bad)

    def test_expired_token_raises(self) -> None:
        """Истёкший токен вызывает ExpiredSignatureError."""
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

    def test_wrong_algorithm_raises(self) -> None:
        """Токен с другим алгоритмом не декодируется."""
        settings = get_settings()
        bad_alg = jwt.encode(
            {
                "sub": "x",
                "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
            },
            settings.jwt_secret,
            algorithm="HS384",
        )
        with pytest.raises(jwt.InvalidTokenError):
            decode_token(bad_alg)

    def test_wrong_secret_raises(self) -> None:
        """Токен, подписанный другим ключом, не декодируется."""
        bad = jwt.encode(
            {
                "sub": "x",
                "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
            },
            "wrong-secret-key-at-least-32!!",
            algorithm="HS256",
        )
        with pytest.raises(jwt.InvalidTokenError):
            decode_token(bad)

    def test_malformed_token_raises(self) -> None:
        """Совсем не JWT-строка вызывает ошибку."""
        with pytest.raises(jwt.InvalidTokenError):
            decode_token("not-a-jwt-at-all")

    def test_empty_token_raises(self) -> None:
        """Пустой токен вызывает ошибку."""
        with pytest.raises(jwt.InvalidTokenError):
            decode_token("")
