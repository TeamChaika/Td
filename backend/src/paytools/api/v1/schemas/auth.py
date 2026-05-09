"""Pydantic-схемы для auth-эндпоинтов и регистрации организации."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from paytools.db.models.enums import OrganizationStatus, UserRole

# ---------------------------------------------------------------------------
# Входные схемы
# ---------------------------------------------------------------------------


class OrganizationRegisterRequest(BaseModel):
    """Тело запроса регистрации организации и первого пользователя."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(description="Email организатора (будет логином)")
    password: str = Field(
        min_length=10,
        max_length=128,
        repr=False,
        description="Пароль, минимум 10 символов. Не участвует в repr() модели.",
    )
    first_name: str = Field(
        min_length=1, max_length=100, description="Имя организатора"
    )
    last_name: str = Field(
        min_length=1, max_length=100, description="Фамилия организатора"
    )
    organization_name: str = Field(
        min_length=1, max_length=255, description="Название организации"
    )
    organization_slug: str = Field(
        min_length=3,
        max_length=64,
        description="Slug организации (латиница, цифры, дефис). "
        "Полная валидация — в доменном сервисе.",
    )
    accept_terms: bool = Field(
        description="Согласие с пользовательским соглашением и офертой"
    )

    @field_validator("accept_terms", mode="after")
    @classmethod
    def must_accept_terms(cls, v: bool) -> bool:
        """Если не приняты условия — ошибка валидации."""
        if not v:
            raise ValueError("Необходимо принять условия пользовательского соглашения")
        return v


class LoginRequest(BaseModel):
    """Тело запроса логина (email + пароль)."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(description="Email пользователя")
    password: str = Field(
        min_length=1,
        repr=False,
        description=(
            "Пароль. min_length=1 — старые пароли могут быть короче текущей политики."
        ),
    )


class MagicLinkRequestSchema(BaseModel):
    """Запрос отправки magic-link на email."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(
        description="Email, на который отправляется ссылка для входа"
    )


class MagicLinkVerifySchema(BaseModel):
    """Запрос подтверждения magic-link токена."""

    model_config = ConfigDict(extra="forbid")

    token: str = Field(
        min_length=16,
        max_length=200,
        description="Токен из magic-link (передаётся как query-параметр или в URL)",
    )


# ---------------------------------------------------------------------------
# Выходные схемы
# ---------------------------------------------------------------------------


class TokenPair(BaseModel):
    """Ответ с access-токеном.

    Refresh-токен возвращается в httpOnly cookie `tdpay_refresh`,
    не в теле ответа. Клиент не имеет к нему доступа из JavaScript.
    """

    access_token: str = Field(description="JWT access-токен")
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(description="Срок жизни access-токена в секундах")


class MeResponse(BaseModel):
    """Информация о текущем пользователе (GET /auth/me)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="ID пользователя")
    email: EmailStr = Field(description="Email пользователя")
    first_name: str | None = Field(default=None, description="Имя")
    last_name: str | None = Field(default=None, description="Фамилия")
    role: UserRole = Field(description="Роль пользователя")
    organization_id: UUID | None = Field(
        default=None, description="ID организации (null у superadmin)"
    )
    organization_slug: str | None = Field(
        default=None, description="Slug организации (null у superadmin)"
    )
    organization_status: OrganizationStatus | None = Field(
        default=None,
        description="Статус организации (null у superadmin)",
    )


class RegisterResponse(BaseModel):
    """Ответ на успешную регистрацию организации."""

    model_config = ConfigDict(from_attributes=True)

    organization_id: UUID = Field(description="ID созданной организации")
    user_id: UUID = Field(description="ID созданного пользователя-организатора")
    status: OrganizationStatus = Field(
        default=OrganizationStatus.PENDING_MODERATION,
        description="Статус организации (ожидаемо PENDING_MODERATION)",
    )
    message: str = Field(
        default="Заявка отправлена на модерацию, мы свяжемся с вами",
        description="Дружелюбное сообщение для пользователя на русском",
    )
