"""Примитивы безопасности: bcrypt, JWT, HMAC, Fernet.

Конкретные сервисы (AuthService, WebhookVerifier) используют эти хелперы.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Final, Literal

import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken
from redis.asyncio import Redis

from paytools.core.config import get_settings

_settings = get_settings()
_JWT_ALGORITHM: Final = "HS256"


# ------------------------ Пароли (bcrypt) ------------------------


def hash_password(password: str) -> str:
    """Хэширует пароль bcrypt с rounds=12."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Проверяет пароль против хэша. Никогда не кидает исключений."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ------------------------ JWT ------------------------


TokenType = Literal["access", "refresh"]


def _create_token(
    payload: dict[str, Any],
    *,
    token_type: TokenType,
    expires_delta: timedelta,
) -> str:
    """Внутренний хелпер: формирует JWT с техническими claim-ами."""
    now = datetime.now(UTC)
    claims: dict[str, Any] = {
        **payload,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "type": token_type,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(claims, _settings.jwt_secret, algorithm=_JWT_ALGORITHM)


def create_access_token(payload: dict[str, Any]) -> str:
    """Создаёт access-токен (короткоживущий, для API-запросов)."""
    return _create_token(
        payload,
        token_type="access",
        expires_delta=timedelta(minutes=_settings.jwt_access_ttl_min),
    )


def create_refresh_token(payload: dict[str, Any]) -> str:
    """Создаёт refresh-токен (долгоживущий, хранится в httpOnly cookie)."""
    return _create_token(
        payload,
        token_type="refresh",
        expires_delta=timedelta(days=_settings.jwt_refresh_ttl_days),
    )


def decode_token(token: str) -> dict[str, Any]:
    """Декодирует и валидирует JWT.

    Бросает `jwt.InvalidTokenError` (подкласс Exception), если токен невалиден
    или истёк. Вызывающий слой должен поймать и преобразовать в AuthError.
    """
    return jwt.decode(token, _settings.jwt_secret, algorithms=[_JWT_ALGORITHM])


# ------------------------ HMAC ------------------------


def hmac_sign(data: str | bytes, secret: str) -> str:
    """Подписывает данные HMAC-SHA256. Результат — hex-строка."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hmac.new(secret.encode("utf-8"), data, hashlib.sha256).hexdigest()


def hmac_verify(data: str | bytes, signature: str, secret: str) -> bool:
    """Проверяет подпись в constant-time."""
    expected = hmac_sign(data, secret)
    return hmac.compare_digest(expected, signature)


# ------------------------ Fernet (симметричное шифрование) ------------------------


def _get_fernet() -> Fernet:
    """Ленивая инициализация Fernet-шифратора из настроек."""
    return Fernet(_settings.fernet_key.encode("utf-8"))


def encrypt_secret(value: str) -> str:
    """Шифрует секрет для хранения в БД (например, QRM API key)."""
    if not value:
        return ""
    return _get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str) -> str:
    """Расшифровывает секрет из БД."""
    if not value:
        return ""
    try:
        return _get_fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Не удалось расшифровать секрет: неверный FERNET_KEY") from exc


# ------------------------ Утилиты ------------------------


def generate_token(length: int = 32) -> str:
    """Случайный URL-safe токен (для magic-link, reset-password, etc.)."""
    import secrets

    return secrets.token_urlsafe(length)


async def revoke_access_token(
    redis: Redis,  # type: ignore[type-arg]
    jti: str,
    exp: int,
) -> None:
    """Добавить access-jti в Redis blacklist на оставшееся время жизни.

    Используется при logout: access-токен становится недействительным
    немедленно, не дожидаясь естественного истечения.
    """
    from datetime import UTC, datetime

    now_ts = int(datetime.now(UTC).timestamp())
    ttl = max(exp - now_ts, 1)
    await redis.setex(f"revoked_jti:{jti}", ttl, "1")
