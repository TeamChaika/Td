"""Репозиторий audit_log — только запись.

Чтение реализуется в Phase 7 (admin audit view).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from paytools.db.models.system import AuditLog
from paytools.db.repositories.base import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    """Репозиторий audit_log — только запись.

    Tenant-фильтр из BaseRepository накладывается, т.к. модель имеет
    колонку organization_id (nullable) — это корректное поведение:
    при создании записи мы всегда передаём organization_id явно,
    а при чтении (в будущем) фильтр защитит от утечки.
    """

    model = AuditLog

    async def log(
        self,
        *,
        action: str,
        organization_id: UUID | None = None,
        user_id: UUID | None = None,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
        data: dict[str, Any] | None = None,
        ip: str | None = None,
    ) -> AuditLog:
        """Создать запись в audit_log.

        Возвращает созданную запись после flush.
        Commit делает вызывающий слой.
        """
        return await self.create(
            action=action,
            organization_id=organization_id,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            data=data,
            ip=ip,
        )
