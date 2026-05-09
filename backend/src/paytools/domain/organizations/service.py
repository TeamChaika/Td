"""Сервисный слой управления организациями.

Отвечает за регистрацию (атомарное создание Organization + первый User),
модерацию (approve/suspend), поиск (по slug/id) и обновление настроек.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import sqlalchemy.exc
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from paytools.core.errors import (
    ConflictError,
    DomainError,
    ForbiddenError,
    NotFoundError,
)
from paytools.core.security import decrypt_secret, encrypt_secret
from paytools.db.models.enums import LegalEntityType, OrganizationStatus, UserRole
from paytools.db.models.organization import Organization
from paytools.db.models.user import User
from paytools.db.repositories.organization import OrganizationRepository
from paytools.db.repositories.user import UserRepository
from paytools.domain.audit.service import AuditService

# --------------------------------------------------------------------------- #
# Доменные ошибки
# --------------------------------------------------------------------------- #


class SlugTakenError(ConflictError):
    """Slug уже занят другой организацией."""

    code = "slug_taken"
    default_message = "Организация с таким slug уже существует"


class EmailTakenError(ConflictError):
    """Пользователь с таким email уже зарегистрирован в системе."""

    code = "email_taken"
    default_message = "Пользователь с таким email уже зарегистрирован"


class RegistrationConflictError(ConflictError):
    """Общий конфликт регистрации (IntegrityError, не распознанный подробно)."""

    code = "registration_conflict"
    default_message = "Конфликт при регистрации"


# --------------------------------------------------------------------------- #
# Входные DTO
# --------------------------------------------------------------------------- #


@dataclass(slots=True, kw_only=True)
class RegisterOrganizationInput:
    """Данные для атомарной регистрации организации с первым пользователем.

    password_hash передан уже захешированным — хеширование выполняется
    в AuthService, чтобы доменный слой организаций не зависел от policy
    паролей и bcrypt.

    organization_slug уже провалидирован через validate_slug в AuthService.
    """

    email: str
    password_hash: str
    first_name: str
    last_name: str
    organization_name: str
    organization_slug: str


# --------------------------------------------------------------------------- #
# Sentinel для PATCH-семантики (отличаем «не передано» от «передано None»)
# --------------------------------------------------------------------------- #


class _Unset:
    """Sentinel-объект: поле не было передано в запросе (PATCH-семантика).

    Используется в UpdateSettingsInput, чтобы отличать «поле не передано»
    от «поле передано со значением None». Синглтон.
    """

    _instance: _Unset | None = None

    def __new__(cls) -> _Unset:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance


UNSET: _Unset = _Unset()


@dataclass
class UpdateSettingsInput:
    """Доменный DTO для PATCH-обновления настроек организации.

    Все поля по умолчанию — UNSET (не переданы). Сервис обновляет только те,
    которые не равны UNSET. Это избавляет доменный слой от зависимости
    от Pydantic (model_dump/exclude_unset).

    qrm_api_key_plain — сырой ключ (будет зашифрован в сервисе).
    """

    brand_name: str | None | _Unset = UNSET
    logo_url: str | None | _Unset = UNSET
    brand_color: str | None | _Unset = UNSET
    contact_email: str | None | _Unset = UNSET
    contact_phone: str | None | _Unset = UNSET
    legal_entity_type: LegalEntityType | None | _Unset = UNSET
    legal_inn: str | None | _Unset = UNSET
    legal_name: str | None | _Unset = UNSET
    legal_address: str | None | _Unset = UNSET
    qrm_api_key_plain: str | None | _Unset = UNSET
    qrm_api_login: str | None | _Unset = UNSET
    qrm_prod_mode: bool | _Unset = UNSET
    telegram_chat_id: int | None | _Unset = UNSET
    refund_policy: str | None | _Unset = UNSET
    timezone: str | _Unset = UNSET


# --------------------------------------------------------------------------- #
# Сервис
# --------------------------------------------------------------------------- #


class OrganizationService:
    """Доменный сервис управления организациями.

    Не открывает и не коммитит транзакцию сам — работает внутри сессии,
    переданной из вызывающего слоя (FastAPI dependency get_session).
    Атомарность обеспечивается через flush внутри методов;
    commit/rollback — зона ответственности get_session.
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        org_repo: OrganizationRepository,
        user_repo: UserRepository,
        audit_service: AuditService | None = None,
        redis: Redis[str] | None = None,
    ) -> None:
        self.session = session
        self.org_repo = org_repo
        self.user_repo = user_repo
        self.audit_service = audit_service
        self.redis = redis

    # --- Регистрация ---

    async def register(
        self, data: RegisterOrganizationInput
    ) -> tuple[Organization, User]:
        """Атомарно создать организацию и первого пользователя-организатора.

        Порядок:
        1. Проверить, что slug и email не заняты (409 Conflict).
        2. Создать Organization со статусом PENDING_MODERATION.
        3. Создать User с ролью ORGANIZER, привязанный к организации.
        4. Вызвать flush — обе записи попадают в БД в одной транзакции.

        Commit не делаем: он произойдёт в get_session после успешного
        возврата из endpoint. Если упадёт исключение — get_session откатит.
        """
        if await self.org_repo.slug_exists(data.organization_slug):
            raise SlugTakenError(details={"field": "organization_slug"})

        if await self.user_repo.email_exists(data.email):
            raise EmailTakenError(details={"field": "email"})

        # Защита от багов на стыке слоёв: AuthService обязан передать slug
        # уже в нижнем регистре, но перепроверим.
        if data.organization_slug != data.organization_slug.lower():
            raise ValueError(
                "organization_slug должен быть в нижнем регистре — "
                "AuthService не привёл slug к нижнему регистру перед вызовом"
            )

        try:
            organization = await self.org_repo.create(
                slug=data.organization_slug,
                name=data.organization_name,
                status=OrganizationStatus.PENDING_MODERATION,
            )

            user = await self.user_repo.create(
                email=data.email.lower(),
                password_hash=data.password_hash,
                first_name=data.first_name,
                last_name=data.last_name,
                role=UserRole.ORGANIZER,
                is_active=True,
                organization_id=organization.id,
            )

            await self.session.flush()
        except sqlalchemy.exc.IntegrityError as exc:
            # TOCTOU-защита: между slug_exists/email_exists и create
            # могла вставиться параллельная регистрация. БД имеет unique
            # constraints — IntegrityError ловится и мапится в доменную ошибку.
            # get_session автоматически откатит транзакцию при перевыбросе.
            raise self._map_integrity_error(exc) from exc

        if self.audit_service is not None:
            await self.audit_service.log_organization_registered(
                organization_id=organization.id,
                by_user=user,
            )

        # Нотификация superadmin'ов будет реализована в Phase 6 (notifications).

        return organization, user

    # --- Модерация ---

    async def approve(self, org_id: UUID, *, by_user: User) -> Organization:
        """Одобрить организацию: перевести статус в ACTIVE.

        Только superadmin имеет право одобрять.
        Если организация уже ACTIVE — идемпотентно возвращает её без изменений.
        """
        org = await self._require_org(org_id)

        if by_user.role != UserRole.SUPERADMIN:
            raise ForbiddenError("Только superadmin может одобрять организации")

        if org.status == OrganizationStatus.ACTIVE:
            return org

        await self.org_repo.set_status(org, OrganizationStatus.ACTIVE)

        await self._invalidate_tenant_cache(org.slug)

        if self.audit_service is not None:
            await self.audit_service.log_organization_approved(
                organization_id=org.id,
                by_user=by_user,
            )

        return org

    async def suspend(
        self, org_id: UUID, *, by_user: User, reason: str
    ) -> Organization:
        """Заблокировать организацию: перевести статус в SUSPENDED.

        Только superadmin имеет право блокировать.
        reason должен быть непустым (defensive-проверка, дублирующая Pydantic).
        Если организация уже SUSPENDED — идемпотентно возвращает её без изменений.
        """
        org = await self._require_org(org_id)

        if by_user.role != UserRole.SUPERADMIN:
            raise ForbiddenError("Только superadmin может блокировать организации")

        if not reason.strip():
            raise ValueError("reason не может быть пустым")

        if org.status == OrganizationStatus.SUSPENDED:
            return org

        await self.org_repo.set_status(org, OrganizationStatus.SUSPENDED)

        await self._invalidate_tenant_cache(org.slug)

        if self.audit_service is not None:
            await self.audit_service.log_organization_suspended(
                organization_id=org.id,
                by_user=by_user,
                reason=reason,
            )

        return org

    # --- Поиск ---

    async def get_by_slug(self, slug: str) -> Organization:
        """Найти организацию по slug (без учёта регистра).

        Если не найдена — 404 NotFoundError.
        """
        org = await self.org_repo.get_by_slug(slug)
        return self._ensure_found(org, "Organization not found", details={"slug": slug})

    async def get_by_id(self, org_id: UUID) -> Organization:
        """Найти организацию по первичному ключу.

        Если не найдена — 404 NotFoundError.
        """
        org = await self.org_repo.get_by_id(org_id)
        return self._ensure_found(
            org, "Organization not found", details={"organization_id": str(org_id)}
        )

    # --- Настройки ---

    async def update_settings(
        self,
        org_id: UUID,
        data: UpdateSettingsInput,
        *,
        by_user: User | None = None,
    ) -> Organization:
        """Обновить настройки организации (PATCH-семантика).

        Принимает доменный DTO UpdateSettingsInput. Поля, равные UNSET,
        не обновляются. Поля со значением None — очищаются.

        Особый случай — qrm_api_key_plain:
        - Если передан непустой ключ — шифруется через encrypt_secret
          и сохраняется в qrm_api_key_encrypted.
        - Если передана пустая строка — ключ очищается (None).
        - Если UNSET — остаётся без изменений.
        """
        org = await self._require_org(org_id)

        changed_fields: list[str] = []

        # Обрабатываем каждое поле независимо — без model_dump
        if not isinstance(data.brand_name, _Unset):
            org.brand_name = data.brand_name
            changed_fields.append("brand_name")

        if not isinstance(data.logo_url, _Unset):
            org.logo_url = data.logo_url
            changed_fields.append("logo_url")

        if not isinstance(data.brand_color, _Unset):
            org.brand_color = data.brand_color
            changed_fields.append("brand_color")

        if not isinstance(data.contact_email, _Unset):
            org.contact_email = data.contact_email
            changed_fields.append("contact_email")

        if not isinstance(data.contact_phone, _Unset):
            org.contact_phone = data.contact_phone
            changed_fields.append("contact_phone")

        if not isinstance(data.legal_entity_type, _Unset):
            org.legal_entity_type = data.legal_entity_type
            changed_fields.append("legal_entity_type")

        if not isinstance(data.legal_inn, _Unset):
            org.legal_inn = data.legal_inn
            changed_fields.append("legal_inn")

        if not isinstance(data.legal_name, _Unset):
            org.legal_name = data.legal_name
            changed_fields.append("legal_name")

        if not isinstance(data.legal_address, _Unset):
            org.legal_address = data.legal_address
            changed_fields.append("legal_address")

        if not isinstance(data.qrm_api_login, _Unset):
            org.qrm_api_login = data.qrm_api_login
            changed_fields.append("qrm_api_login")

        if not isinstance(data.qrm_prod_mode, _Unset):
            org.qrm_prod_mode = data.qrm_prod_mode
            changed_fields.append("qrm_prod_mode")

        if not isinstance(data.telegram_chat_id, _Unset):
            org.telegram_chat_id = data.telegram_chat_id
            changed_fields.append("telegram_chat_id")

        if not isinstance(data.refund_policy, _Unset):
            org.refund_policy = data.refund_policy
            changed_fields.append("refund_policy")

        if not isinstance(data.timezone, _Unset):
            org.timezone = data.timezone
            changed_fields.append("timezone")

        if not isinstance(data.qrm_api_key_plain, _Unset):
            raw_key = data.qrm_api_key_plain
            if raw_key == "":
                org.qrm_api_key_encrypted = None
            elif raw_key is not None:
                org.qrm_api_key_encrypted = encrypt_secret(raw_key)
            changed_fields.append("qrm_api_key")

        await self.session.flush()

        # После flush() БД обновила updated_at через onupdate=func.now(),
        # но Python-объект org имеет stale-значение. refresh() синхронизирует
        # объект с БД, чтобы model_validate(org) в API-слое не спровоцировал
        # async lazy-load → MissingGreenlet.
        await self.session.refresh(org)

        # Инвалидируем кеш tenant (на случай смены slug или статуса)
        await self._invalidate_tenant_cache(org.slug)

        if self.audit_service is not None and by_user is not None:
            await self.audit_service.log_settings_updated(
                organization_id=org.id,
                by_user=by_user,
                changed_fields=changed_fields,
            )
            # Отдельное событие для обновления QRM-ключа
            # (аудит безопасности / бухгалтерии)
            if "qrm_api_key" in changed_fields:
                await self.audit_service.log_qrm_key_updated(
                    organization_id=org.id,
                    by_user=by_user,
                )

        return org

    # --- Маскирование QRM-ключа ---

    def mask_qrm_key(self, encrypted_key: str | None) -> str | None:
        """Синхронный хелпер для API-слоя: маскировать зашифрованный QRM-ключ.

        Результат: ``"****" + last_4_chars``, или ``"****"`` если ключ короче
        4 символов либо расшифровка упала.

        Сырой ключ никогда не возвращается из API — только маскированное
        представление.
        """
        if not encrypted_key:
            return None

        try:
            raw = decrypt_secret(encrypted_key)
        except ValueError:
            # Не палим ошибку пользователю, но оставляем визуальный намёк
            # что ключ есть (маскированная строка).
            return "****"

        if len(raw) < 4:
            return "****"

        return "****" + raw[-4:]

    # ----------------------------------------------------------------------- #
    # Приватные хелперы
    # ----------------------------------------------------------------------- #

    @staticmethod
    def _map_integrity_error(exc: sqlalchemy.exc.IntegrityError) -> DomainError:
        """Транслировать IntegrityError из БД в доменную ошибку.

        Парсит constraint_name или текст ошибки, чтобы определить,
        какой именно unique constraint нарушен (slug или email).
        Если не удалось распарсить — возвращает общий ConflictError.
        """
        orig = str(exc.orig) if exc.orig is not None else ""
        constraint: str | None = (
            getattr(exc.orig, "constraint_name", None) if exc.orig is not None else None
        )

        # Проверяем по имени constraint (PostgreSQL)
        if constraint:
            if "slug" in constraint.lower():
                return SlugTakenError(details={"field": "organization_slug"})
            if "email" in constraint.lower():
                return EmailTakenError(details={"field": "email"})

        # Fallback: парсим текст ошибки
        orig_lower = orig.lower()
        if (
            "organizations_slug_key" in orig_lower
            or "uq_organizations_slug" in orig_lower
        ):
            return SlugTakenError(details={"field": "organization_slug"})
        if "users_email_key" in orig_lower or "uq_users_email" in orig_lower:
            return EmailTakenError(details={"field": "email"})

        # Не удалось определить — общий конфликт
        return RegistrationConflictError()

    async def _require_org(self, org_id: UUID) -> Organization:
        """Загрузить организацию или выбросить NotFoundError.

        Вспомогательный метод, чтобы не дублировать проверку на None
        в каждом публичном методе.
        """
        org = await self.org_repo.get_by_id(org_id)
        return self._ensure_found(
            org,
            "Organization not found",
            details={"organization_id": str(org_id)},
        )

    async def _invalidate_tenant_cache(self, slug: str) -> None:
        """Инвалидировать кеш tenant slug → org_id в Redis.

        Вызывается при смене статуса организации (approve/suspend),
        чтобы middleware не отдавал устаревший статус.
        Если Redis не настроен — молча пропускаем.
        """
        if self.redis is not None:
            try:
                await self.redis.delete(f"tenant_slug:{slug.lower()}")
            except Exception:
                pass

    @staticmethod
    def _ensure_found(
        org: Organization | None,
        message: str,
        *,
        details: dict[str, str],
    ) -> Organization:
        if org is None:
            raise NotFoundError(message, details=details)
        return org
