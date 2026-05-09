"""Сервис аудита — логирование критичных действий.

Не коммитит транзакцию — работает в рамках переданной session.
Commit делает вызывающий слой (get_session).
"""

from __future__ import annotations

from typing import Final
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from paytools.db.models.system import AuditLog
from paytools.db.models.user import User
from paytools.db.repositories.audit import AuditLogRepository


class AuditAction:
    """Константы-идентификаторы действий для audit log.

    Формат: ``<resource>.<action>`` — например, ``organization.approve``.
    """

    ORG_REGISTER: Final[str] = "organization.register"
    ORG_APPROVE: Final[str] = "organization.approve"
    ORG_SUSPEND: Final[str] = "organization.suspend"
    ORG_UPDATE_SETTINGS: Final[str] = "organization.update_settings"
    ORG_QRM_KEY_UPDATED: Final[str] = "organization.qrm_key_updated"

    USER_LOGIN: Final[str] = "user.login"
    USER_LOGOUT: Final[str] = "user.logout"
    USER_MAGIC_LINK_REQUESTED: Final[str] = "user.magic_link_requested"
    USER_MAGIC_LINK_VERIFIED: Final[str] = "user.magic_link_verified"


class AuditService:
    """Лог критичных действий.

    Не коммитит транзакцию — работает в рамках переданной session.
    Commit делает вызывающий слой (get_session).
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        repo: AuditLogRepository,
    ) -> None:
        self.session = session
        self.repo = repo

    async def log_organization_approved(
        self,
        *,
        organization_id: UUID,
        by_user: User,
        ip: str | None = None,
    ) -> AuditLog:
        """Зафиксировать approve организации."""
        return await self.repo.log(
            action=AuditAction.ORG_APPROVE,
            organization_id=organization_id,
            user_id=by_user.id,
            resource_type="organization",
            resource_id=organization_id,
            data={"by_email": by_user.email},
            ip=ip,
        )

    async def log_organization_suspended(
        self,
        *,
        organization_id: UUID,
        by_user: User,
        reason: str,
        ip: str | None = None,
    ) -> AuditLog:
        """Зафиксировать suspend организации."""
        return await self.repo.log(
            action=AuditAction.ORG_SUSPEND,
            organization_id=organization_id,
            user_id=by_user.id,
            resource_type="organization",
            resource_id=organization_id,
            data={"by_email": by_user.email, "reason": reason},
            ip=ip,
        )

    async def log_organization_registered(
        self,
        *,
        organization_id: UUID,
        by_user: User,
        ip: str | None = None,
    ) -> AuditLog:
        """Зафиксировать регистрацию новой организации."""
        return await self.repo.log(
            action=AuditAction.ORG_REGISTER,
            organization_id=organization_id,
            user_id=by_user.id,
            resource_type="organization",
            resource_id=organization_id,
            ip=ip,
        )

    async def log_settings_updated(
        self,
        *,
        organization_id: UUID,
        by_user: User,
        changed_fields: list[str],
        ip: str | None = None,
    ) -> AuditLog:
        """Зафиксировать обновление настроек организации.

        changed_fields — список имён изменённых полей
        (например, ["brand_name", "qrm_api_key"]). Значения не пишем,
        т.к. среди них могут быть чувствительные данные.
        """
        return await self.repo.log(
            action=AuditAction.ORG_UPDATE_SETTINGS,
            organization_id=organization_id,
            user_id=by_user.id,
            resource_type="organization",
            resource_id=organization_id,
            data={"by_email": by_user.email, "changed_fields": changed_fields},
            ip=ip,
        )

    async def log_qrm_key_updated(
        self,
        *,
        organization_id: UUID,
        by_user: User,
        ip: str | None = None,
    ) -> AuditLog:
        """Зафиксировать обновление QRM-ключа отдельным событием."""
        return await self.repo.log(
            action=AuditAction.ORG_QRM_KEY_UPDATED,
            organization_id=organization_id,
            user_id=by_user.id,
            resource_type="organization",
            resource_id=organization_id,
            ip=ip,
        )

    async def log_user_login(
        self,
        *,
        user: User,
        ip: str | None = None,
        method: str = "password",
    ) -> AuditLog:
        """Зафиксировать вход пользователя (password или magic_link)."""
        return await self.repo.log(
            action=AuditAction.USER_LOGIN,
            organization_id=user.organization_id,
            user_id=user.id,
            resource_type="user",
            resource_id=user.id,
            data={"method": method, "email": user.email},
            ip=ip,
        )

    async def log_user_logout(
        self,
        *,
        user: User,
        ip: str | None = None,
    ) -> AuditLog:
        """Зафиксировать выход пользователя."""
        return await self.repo.log(
            action=AuditAction.USER_LOGOUT,
            organization_id=user.organization_id,
            user_id=user.id,
            resource_type="user",
            resource_id=user.id,
            data={"email": user.email},
            ip=ip,
        )

    async def log_magic_link_requested(
        self,
        *,
        user: User,
        ip: str | None = None,
    ) -> AuditLog:
        """Зафиксировать запрос magic-link."""
        return await self.repo.log(
            action=AuditAction.USER_MAGIC_LINK_REQUESTED,
            organization_id=user.organization_id,
            user_id=user.id,
            resource_type="user",
            resource_id=user.id,
            data={"email": user.email},
            ip=ip,
        )

    async def log_magic_link_verified(
        self,
        *,
        user: User,
        ip: str | None = None,
    ) -> AuditLog:
        """Зафиксировать успешную верификацию magic-link."""
        return await self.repo.log(
            action=AuditAction.USER_MAGIC_LINK_VERIFIED,
            organization_id=user.organization_id,
            user_id=user.id,
            resource_type="user",
            resource_id=user.id,
            data={"email": user.email},
            ip=ip,
        )
