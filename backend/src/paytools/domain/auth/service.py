"""Сервисный слой аутентификации.

Отвечает за регистрацию организации с первым пользователем (signup),
логин по email+паролю, refresh/rotating refresh-токенов, logout
и ручную верификацию access-токенов.

Magic-link вынесен в отдельный модуль (задача 2a.6).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from paytools.core.config import Settings, get_settings
from paytools.core.errors import (
    AuthError,
    OrganizationSuspendedError,
)
from paytools.core.redis import _RedisType
from paytools.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from paytools.db.models.organization import Organization
from paytools.db.models.user import User
from paytools.db.repositories.email_blocklist import EmailBlocklistRepository
from paytools.db.repositories.organization import OrganizationRepository
from paytools.db.repositories.user import UserRepository
from paytools.domain.audit.service import AuditService
from paytools.domain.auth.errors import (
    EmailBlockedError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    OrganizationPendingError,
    PasswordTooWeakError,
    SlugInvalidError,
)
from paytools.domain.organizations.service import (
    OrganizationService,
    RegisterOrganizationInput,
)
from paytools.domain.organizations.validation import SlugValidationError, validate_slug

# --------------------------------------------------------------------------- #
# DTO
# --------------------------------------------------------------------------- #


@dataclass(slots=True, kw_only=True)
class SignupInput:
    """Данные для регистрации организации с первым пользователем.

    Все поля — сырые значения от клиента. Валидация и нормализация
    выполняются внутри AuthService.signup_organization.
    """

    email: str
    password: str
    first_name: str
    last_name: str
    organization_name: str
    organization_slug: str


@dataclass(slots=True, kw_only=True)
class TokenPair:
    """Пара токенов, выдаваемая при логине / refresh.

    В отличие от Pydantic-схемы TokenPair в api/v1/schemas/auth.py,
    этот DTO содержит оба токена + access_expires_in.
    API-схема отдаёт только access_token в теле ответа,
    refresh уходит в httpOnly cookie.
    """

    access_token: str
    refresh_token: str
    access_expires_in: int  # секунды до истечения access


# --------------------------------------------------------------------------- #
# Константы
# --------------------------------------------------------------------------- #

_MIN_PASSWORD_LENGTH: int = 10
"""Минимальная длина пароля согласно password policy."""


# --------------------------------------------------------------------------- #
# Сервис
# --------------------------------------------------------------------------- #


class AuthService:
    """Доменный сервис аутентификации.

    Не открывает и не коммитит транзакцию сам — работает внутри сессии,
    переданной из вызывающего слоя (FastAPI dependency get_session).
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        user_repo: UserRepository,
        org_service: OrganizationService,
        redis: _RedisType,
        email_blocklist_repo: EmailBlocklistRepository | None = None,
        org_repo: OrganizationRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        self.session = session
        self.user_repo = user_repo
        self.org_service = org_service
        self.redis = redis
        self.email_blocklist_repo = email_blocklist_repo
        self.org_repo = org_repo
        self.audit_service = audit_service
        self._settings: Settings = get_settings()

    # --- Регистрация ---

    async def signup_organization(self, data: SignupInput) -> tuple[Organization, User]:
        """Атомарно зарегистрировать организацию с первым пользователем.

        Порядок:
        1. Проверить пароль на соответствие policy (min 10 символов).
        2. Провалидировать slug через validate_slug.
        3. Нормализовать email и slug (strip + lower).
        4. Захешировать пароль.
        5. Вызвать OrganizationService.register для атомарного создания.

        TokenPair не возвращается: организация создаётся в статусе
        PENDING_MODERATION, логин до approve невозможен — проверка статуса
        организации выполняется в методе login.

        Raises:
            PasswordTooWeakError: пароль короче 10 символов.
            SlugInvalidError: slug не прошёл валидацию.
            SlugTakenError: slug уже занят.
            EmailTakenError: email уже зарегистрирован.
            ValidationError: email в блоклисте (disposable-почта).
        """
        # 0. Email blocklist check — до любой бизнес-логики
        if (
            self.email_blocklist_repo is not None
            and await self.email_blocklist_repo.is_blocked(data.email)
        ):
            raise EmailBlockedError()

        # 1. Password policy
        if len(data.password) < _MIN_PASSWORD_LENGTH:
            raise PasswordTooWeakError(details={"min_length": _MIN_PASSWORD_LENGTH})

        # 2. Slug validation
        try:
            validate_slug(data.organization_slug)
        except SlugValidationError as err:
            raise SlugInvalidError(
                message=f"Некорректный slug: {err}",
                details={"code": err.code},
            ) from err

        # 3. Нормализация
        email = data.email.strip().lower()
        slug = data.organization_slug.strip().lower()

        # 4. Hash password
        password_hash = hash_password(data.password)

        # 5. Атомарное создание через OrganizationService
        input_data = RegisterOrganizationInput(
            email=email,
            password_hash=password_hash,
            first_name=data.first_name,
            last_name=data.last_name,
            organization_name=data.organization_name,
            organization_slug=slug,
        )

        return await self.org_service.register(input_data)

    # --- Логин ---

    async def login(
        self,
        email: str,
        password: str,
        *,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> TokenPair:
        """Аутентифицировать пользователя по email и паролю.

        Возвращает пару токенов (access + refresh). Refresh-токен
        должен быть установлен в httpOnly cookie на стороне API-слоя.

        Все ошибки аутентификации возвращают одинаковое сообщение
        «Неверный email или пароль» — не раскрываем, существует ли
        пользователь с таким email.

        Raises:
            InvalidCredentialsError: неверный email, пароль, или
                пользователь деактивирован / не имеет пароля.
        """
        email = email.strip().lower()

        user = await self.user_repo.get_by_email(email)
        if user is None:
            raise InvalidCredentialsError()

        # Пользователь без пароля (например, создан только через Telegram)
        if user.password_hash is None:
            raise InvalidCredentialsError()

        if not verify_password(password, user.password_hash):
            raise InvalidCredentialsError()

        if not user.is_active:
            raise InvalidCredentialsError()

        # Проверка статуса организации для organizer'ов
        if (
            user.role.value == "organizer"
            and user.organization_id is not None
            and self.org_repo is not None
        ):
            org = await self.org_repo.get_by_id(user.organization_id)
            if org is not None:
                if org.status.value == "suspended":
                    raise OrganizationSuspendedError()
                if org.status.value == "pending_moderation":
                    raise OrganizationPendingError()

        await self.user_repo.update_last_login(user)

        # Аудит входа (не падает при ошибке аудита)
        if self.audit_service is not None:
            try:
                await self.audit_service.log_user_login(
                    user=user, ip=ip, method="password"
                )
            except Exception:
                import logging

                logging.getLogger(__name__).warning(
                    "Не удалось записать аудит входа user=%s",
                    user.id,
                    exc_info=True,
                )

        return self.issue_tokens(user)

    # --- Refresh ---

    async def refresh(self, refresh_token: str) -> TokenPair:
        """Обновить пару токенов по refresh-токену (rotating refresh).

        Старый refresh-токен добавляется в блок-лист Redis —
        один refresh-токен можно использовать только один раз.
        Новый refresh-токен должен заменить старый в cookie.

        Raises:
            InvalidRefreshTokenError: токен невалиден, истёк, отозван,
                или пользователь деактивирован.
        """
        # 1. Декодируем токен
        try:
            payload = decode_token(refresh_token)
        except jwt.InvalidTokenError as exc:
            raise InvalidRefreshTokenError() from exc

        # 2. Проверяем тип токена
        if payload.get("type") != "refresh":
            raise InvalidRefreshTokenError()

        jti: str | None = payload.get("jti")
        if jti is None:
            raise InvalidRefreshTokenError()

        # 3. Проверяем блок-лист
        if await self.redis.exists(f"revoked_jti:{jti}"):
            raise InvalidRefreshTokenError()

        # 4. Загружаем пользователя
        sub_raw: str | None = payload.get("sub")
        if sub_raw is None:
            raise InvalidRefreshTokenError()

        try:
            sub = UUID(sub_raw)
        except ValueError as exc:
            raise InvalidRefreshTokenError() from exc

        user = await self.user_repo.get_by_id(sub)
        if user is None or not user.is_active:
            raise InvalidRefreshTokenError()

        # 5. Атомарно захватываем старый jti в блок-лист (SET NX).
        # Если два параллельных запроса с одним refresh-токеном —
        # только первый получит True, второй получит None и ошибку.
        # TTL = оставшееся время жизни refresh-токена, но не менее 1 сек.
        now_ts = int(datetime.now(UTC).timestamp())
        exp_ts: int = payload.get("exp", now_ts)
        ttl_seconds = max(exp_ts - now_ts, 1)
        # Используем refresh TTL из настроек как верхнюю границу
        refresh_ttl_seconds = self._settings.jwt_refresh_ttl_days * 86400
        block_ttl = min(ttl_seconds, refresh_ttl_seconds)

        claimed = await self.redis.set(f"revoked_jti:{jti}", "1", ex=block_ttl, nx=True)
        if not claimed:
            # Ключ уже существует — параллельный запрос уже захватил jti
            raise InvalidRefreshTokenError()

        # 6. Выдаём новую пару (только после успешного NX-захвата)
        new_tokens = self.issue_tokens(user)

        return new_tokens

    # --- Logout ---

    async def logout(
        self,
        refresh_token: str,
        *,
        access_jti: str | None = None,
        access_exp: int | None = None,
        user: User | None = None,
        ip: str | None = None,
    ) -> None:
        """Разлогинить пользователя: добавить refresh-токен в блок-лист.

        Если передан access_jti/access_exp — access-токен тоже ревокается.
        Идемпотентный: если токен невалиден или уже в блок-листе —
        молча завершается. Результат в любом случае один: пользователь
        разлогинен, повторное использование токенов невозможно.
        """
        # Ревокация refresh-токена
        try:
            payload = decode_token(refresh_token)
        except jwt.InvalidTokenError:
            # Токен невалиден — logout и так достигнут
            pass
        else:
            jti: str | None = payload.get("jti")
            if jti is not None:
                now_ts = int(datetime.now(UTC).timestamp())
                exp_ts: int = payload.get("exp", now_ts)
                ttl_seconds = max(exp_ts - now_ts, 1)
                await self.redis.setex(f"revoked_jti:{jti}", ttl_seconds, "1")

        # Ревокация access-токена (отдельный jti)
        if access_jti is not None and access_exp is not None:
            now_ts = int(datetime.now(UTC).timestamp())
            ttl_seconds = max(access_exp - now_ts, 1)
            await self.redis.setex(f"revoked_jti:{access_jti}", ttl_seconds, "1")

        # Аудит выхода
        if self.audit_service is not None and user is not None:
            try:
                await self.audit_service.log_user_logout(user=user, ip=ip)
            except Exception:
                import logging

                logging.getLogger(__name__).warning(
                    "Не удалось записать аудит выхода user=%s",
                    user.id,
                    exc_info=True,
                )

    # --- Verify access ---

    async def verify_access(self, access_token: str) -> User:
        """Вручную провалидировать access-токен и вернуть пользователя.

        Используется вне FastAPI-depends: WebSocket, фоновые задачи,
        внутренние вызовы между сервисами.

        Raises:
            AuthError: токен невалиден, истёк, не access-типа,
                или пользователь не найден / деактивирован.
        """
        # 1. Декодируем
        try:
            payload = decode_token(access_token)
        except jwt.InvalidTokenError as exc:
            raise AuthError("Access-токен недействителен") from exc

        # 2. Проверяем тип
        if payload.get("type") != "access":
            raise AuthError("Токен не является access-токеном")

        # 3. Загружаем пользователя
        sub_raw: str | None = payload.get("sub")
        if sub_raw is None:
            raise AuthError("Токен не содержит sub")

        try:
            sub = UUID(sub_raw)
        except ValueError as exc:
            raise AuthError("Некорректный sub в токене") from exc

        user = await self.user_repo.get_by_id(sub)
        if user is None:
            raise AuthError("Пользователь не найден")

        # 4. Проверяем is_active
        if not user.is_active:
            raise AuthError("Пользователь деактивирован")

        return user

    # ----------------------------------------------------------------------- #
    # Хелперы
    # ----------------------------------------------------------------------- #

    def issue_tokens(self, user: User) -> TokenPair:
        """Выпустить пару access + refresh токенов для пользователя.

        Полезная нагрузка токенов включает sub, org, role —
        этого достаточно для tenant middleware и проверки прав.
        """
        payload: dict[str, str | None] = {
            "sub": str(user.id),
            "org": str(user.organization_id) if user.organization_id else None,
            "role": user.role.value,
        }
        access = create_access_token(payload)
        refresh = create_refresh_token(payload)
        access_expires_in = self._settings.jwt_access_ttl_min * 60
        return TokenPair(
            access_token=access,
            refresh_token=refresh,
            access_expires_in=access_expires_in,
        )
