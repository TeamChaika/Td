"""Pydantic-схемы для организации: публичные, организатор, админ."""

import re
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from paytools.db.models.enums import LegalEntityType, OrganizationStatus

# ---------------------------------------------------------------------------
# Публичные (без auth, tenant resolve)
# ---------------------------------------------------------------------------


class PublicTenantResolveResponse(BaseModel):
    """Ответ для фронтового middleware: брендинг организации до логина.

    Используется middleware фронта для рендеринга логотипа, цветовой схемы
    и названия на странице логина до того, как пользователь авторизовался.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="ID организации")
    slug: str = Field(description="Slug организации (поддомен)")
    brand_name: str | None = Field(default=None, description="Брендовое название")
    name: str = Field(description="Юридическое/официальное название")
    logo_url: str | None = Field(default=None, description="URL логотипа")
    brand_color: str | None = Field(default=None, description="Брендовый цвет #RRGGBB")
    status: OrganizationStatus = Field(description="Статус организации")


# ---------------------------------------------------------------------------
# Организатор (self-read/update)
# ---------------------------------------------------------------------------


class OrganizationRead(BaseModel):
    """Полная информация об организации для организатора.

    Обрати внимание: qrm_api_key_encrypted НЕ возвращается — только маскированное
    представление `qrm_api_key_masked` вида ``****abcd``.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="ID организации")
    slug: str = Field(description="Slug организации")
    name: str = Field(description="Название организации")
    brand_name: str | None = Field(default=None, description="Брендовое название")
    logo_url: str | None = Field(default=None, description="URL логотипа")
    brand_color: str | None = Field(default=None, description="Брендовый цвет #RRGGBB")
    contact_email: str | None = Field(default=None, description="Публичный email")
    contact_phone: str | None = Field(default=None, description="Публичный телефон")
    legal_entity_type: LegalEntityType | None = Field(
        default=None, description="Тип юрлица (ИП/ООО/самозанятый/другое)"
    )
    legal_inn: str | None = Field(default=None, description="ИНН")
    legal_name: str | None = Field(default=None, description="Юридическое наименование")
    legal_address: str | None = Field(default=None, description="Юридический адрес")
    qrm_api_key_masked: str | None = Field(
        default=None,
        description=(
            "Маскированный ключ QRM, например '****abcd'. Сам encrypted ключ не отдаём."
        ),
    )
    qrm_api_login: str | None = Field(default=None, description="Логин QRM")
    qrm_prod_mode: bool = Field(description="QRM в режиме prod (не тестовый)")
    telegram_chat_id: int | None = Field(
        default=None, description="ID Telegram-чата для уведомлений"
    )
    refund_policy: str | None = Field(default=None, description="Политика возвратов")
    auto_publish_enabled: bool = Field(
        description="Автоматическая публикация событий без модерации"
    )
    status: OrganizationStatus = Field(description="Статус организации")
    timezone: str = Field(description="Часовой пояс (iana-формат)")
    created_at: datetime = Field(description="Дата создания")
    updated_at: datetime = Field(description="Дата последнего обновления")


class OrganizationUpdateRequest(BaseModel):
    """PATCH-запрос на обновление настроек организации.

    Все поля опциональны — обновляются только переданные.
    ``extra="forbid"`` — случайные поля не пройдут.
    """

    model_config = ConfigDict(extra="forbid")

    brand_name: str | None = Field(default=None, description="Брендовое название")
    logo_url: str | None = Field(default=None, description="URL логотипа")
    brand_color: str | None = Field(
        default=None, description="Брендовый цвет в формате #RRGGBB"
    )
    contact_email: EmailStr | None = Field(default=None, description="Публичный email")
    contact_phone: str | None = Field(default=None, description="Публичный телефон")
    legal_entity_type: LegalEntityType | None = Field(
        default=None, description="Тип юрлица"
    )
    legal_inn: str | None = Field(
        default=None, min_length=2, max_length=12, description="ИНН (2–12 символов)"
    )
    legal_name: str | None = Field(default=None, description="Юридическое наименование")
    legal_address: str | None = Field(default=None, description="Юридический адрес")
    qrm_api_key: str | None = Field(
        default=None,
        description=(
            "Сырой ключ QRM, будет зашифрован при сохранении. Не сохраняется в логах."
        ),
    )
    qrm_api_login: str | None = Field(default=None, description="Логин QRM")
    qrm_prod_mode: bool | None = Field(
        default=None, description="Переключить QRM в prod-режим"
    )
    telegram_chat_id: int | None = Field(
        default=None, description="ID Telegram-чата для уведомлений"
    )
    refund_policy: str | None = Field(default=None, description="Политика возвратов")
    timezone: str | None = Field(
        default=None, description="Часовой пояс (iana-формат, например 'Europe/Moscow')"
    )

    @field_validator("brand_color", mode="after")
    @classmethod
    def validate_brand_color(cls, v: str | None) -> str | None:
        """Если задан — должен быть в формате #RRGGBB (6 hex-цифр)."""
        if v is None:
            return v
        if not re.match(r"^#[0-9A-Fa-f]{6}$", v):
            raise ValueError(
                "brand_color должен быть в формате #RRGGBB, например #FF5500"
            )
        return v


# ---------------------------------------------------------------------------
# QRM test
# ---------------------------------------------------------------------------


class QRMTestRequest(BaseModel):
    """Запрос проверки QRM-ключа.

    Ключ опционален: если не передан — сервис использует сохранённый ключ организации.
    Это удобно при настройке: можно проверить ad-hoc ключ перед сохранением,
    либо проверить уже сохранённый.
    """

    model_config = ConfigDict(extra="forbid")

    qrm_api_key: str | None = Field(
        default=None,
        description=(
            "Сырой ключ для ad-hoc проверки. Если None — используется сохранённый."
        ),
    )


class QRMTestResponse(BaseModel):
    """Результат проверки QRM-ключа."""

    ok: bool = Field(description="Успешность проверки")
    message: str = Field(description="Человекочитаемый результат проверки")
    details: dict[str, Any] | None = Field(
        default=None, description="Детали ответа от QRM API (если есть)"
    )


# ---------------------------------------------------------------------------
# Админ (модерация)
# ---------------------------------------------------------------------------


class AdminOrganizationListItem(BaseModel):
    """Строка таблицы организаций в админке.

    ``owner_email`` — email первого организатора; заполняется сервисом
    при формировании списка, не маппится напрямую из модели.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="ID организации")
    slug: str = Field(description="Slug организации")
    name: str = Field(description="Название организации")
    status: OrganizationStatus = Field(description="Статус организации")
    created_at: datetime = Field(description="Дата создания")
    owner_email: str | None = Field(
        default=None,
        description="Email первого организатора (заполняется сервисом)",
    )


class SuspendRequest(BaseModel):
    """Тело запроса на блокировку организации."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(
        min_length=3,
        max_length=500,
        description="Причина блокировки (отображается организатору и в аудит-логе)",
    )
