"""Конфигурация приложения через pydantic-settings.

Все параметры читаются из переменных окружения и/или `.env`.
Значения env-переменных перекрывают значения из файла.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Глобальные настройки TD Pay backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Окружение ---
    env: Literal["dev", "test", "staging", "prod"] = "dev"

    # --- База данных ---
    database_url: str
    # Пример: postgresql+asyncpg://tdpay:tdpay@postgres:5432/tdpay

    # --- Redis ---
    redis_url: str
    # Пример: redis://redis:6379/0

    # --- Секреты ---
    # Используем обычные str, а не SecretStr, чтобы проще передавать в библиотеки.
    # Никогда не логируем эти поля.
    secret_key: str = Field(min_length=32)
    fernet_key: str  # base64-кодированный, 44 символа
    jwt_secret: str = Field(min_length=32)
    jwt_access_ttl_min: int = 15
    jwt_refresh_ttl_days: int = 30

    # --- S3 / объектное хранилище ---
    s3_endpoint: str
    s3_public_endpoint: str = (
        ""  # URL для формирования публичных ссылок (если отличается от s3_endpoint)
    )
    s3_bucket: str = "tdpay"
    s3_access_key: str
    s3_secret_key: str
    s3_region: str = "ru-1"

    # --- SMTP ---
    smtp_host: str
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str
    smtp_tls: bool = False

    # --- SMS Aero ---
    smsaero_email: str = ""
    smsaero_api_key: str = ""
    smsaero_sign: str = "TDPay"

    # --- QR Manager ---
    qrm_base_url: str = "https://app.devwapiserv.qrm.ooo"
    qrm_test_api_key: str = ""

    # --- Telegram ---
    telegram_bot_token: str = ""
    telegram_bot_username: str = ""

    # --- Платформа ---
    platform_domain: str = "tdpay.local"
    platform_url: str = "http://localhost:3000"
    platform_commission_pct: float = 0.8

    # --- Feature flags ---
    enable_rate_limits: bool = False
    enable_captcha: bool = False

    # --- Postgres credentials (дублируются для docker-compose) ---
    postgres_user: str = "tdpay"
    postgres_password: str = "tdpay"
    postgres_db: str = "tdpay"

    @field_validator("database_url")
    @classmethod
    def _validate_database_url(cls, v: str) -> str:
        """Гарантируем использование async-драйвера."""
        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "DATABASE_URL должен начинаться с postgresql+asyncpg:// "
                "(используется async-движок)."
            )
        return v

    @field_validator("fernet_key")
    @classmethod
    def _validate_fernet_key(cls, v: str) -> str:
        """Проверяем что ключ имеет валидный формат Fernet."""
        if not v:
            raise ValueError(
                "FERNET_KEY не задан. Сгенерируй через "
                "`python -c 'from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())'`."
            )
        # Fernet-ключ — 44-символьный base64
        if len(v) != 44:
            raise ValueError(
                "FERNET_KEY должен быть длиной 44 символа "
                "(base64-кодированные 32 байта)."
            )
        return v

    @property
    def is_dev(self) -> bool:
        return self.env == "dev"

    @property
    def is_prod(self) -> bool:
        return self.env == "prod"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Возвращает singleton-инстанс настроек.

    Кэширование исключает повторную валидацию при каждом вызове.
    """
    return Settings()
