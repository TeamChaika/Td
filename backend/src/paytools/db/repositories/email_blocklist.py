"""Репозиторий для проверки email-блоклиста (disposable-почта)."""

from __future__ import annotations

from sqlalchemy import func, select

from paytools.db.models.system import EmailBlocklist
from paytools.db.repositories.base import BaseRepository


class EmailBlocklistRepository(BaseRepository[EmailBlocklist]):
    """Репозиторий для проверки email-адресов на блокировку.

    Проверяет доменную часть email (всё после ``@``) на наличие
    в таблице email_blocklist. Сравнение регистро-нечувствительное.
    """

    model = EmailBlocklist

    async def is_blocked(self, email: str) -> bool:
        """Проверить, заблокирован ли email (по домену, case-insensitive).

        Возвращает True, если домен email найден в блоклисте.
        """
        if "@" not in email:
            return False

        domain = email.rsplit("@", maxsplit=1)[-1].strip().lower()
        if not domain:
            return False

        stmt = select(1).where(func.lower(EmailBlocklist.domain) == domain)
        result = await self.session.execute(stmt)
        return result.scalar() is not None
