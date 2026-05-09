"""Magic-link аутентификация.

Одноразовая ссылка для входа без пароля. Токен генерируется через
``secrets.token_urlsafe``, хранится в Redis 15 минут, удаляется
атомарно при первом использовании (GETDEL).
"""

from __future__ import annotations

import json
from datetime import timedelta
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from paytools.core.errors import OrganizationSuspendedError
from paytools.core.security import generate_token
from paytools.db.repositories.email_blocklist import EmailBlocklistRepository
from paytools.db.repositories.organization import OrganizationRepository
from paytools.db.repositories.user import UserRepository
from paytools.domain.audit.service import AuditService
from paytools.domain.auth.errors import (
    InvalidMagicLinkError,
    OrganizationPendingError,
)
from paytools.domain.auth.service import AuthService, TokenPair

# --------------------------------------------------------------------------- #
# Сервис
# --------------------------------------------------------------------------- #


class MagicLinkService:
    """Flow входа по одноразовой ссылке на email.

    Токен живёт 15 минут, удаляется после первого использования (one-time).
    Хранится в Redis под ключом ``magic:{token}`` как JSON:
    ``{"email": "user@example.com", "user_id": "<uuid>"}``.
    """

    TOKEN_TTL: timedelta = timedelta(minutes=15)
    TOKEN_LENGTH: int = 32  # байт → base64 URL-safe ~43 символа

    _MIN_TOKEN_LENGTH: int = 16
    _MAX_TOKEN_LENGTH: int = 200

    def __init__(
        self,
        session: AsyncSession,
        *,
        user_repo: UserRepository,
        auth_service: AuthService,
        redis: Redis[str],
        email_blocklist_repo: EmailBlocklistRepository | None = None,
        org_repo: OrganizationRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        self.session = session
        self.user_repo = user_repo
        self.auth_service = auth_service
        self.redis = redis
        self.email_blocklist_repo = email_blocklist_repo
        self.org_repo = org_repo
        self.audit_service = audit_service

    # --- Запрос magic-link ---

    async def request_magic_link(self, email: str) -> None:
        """Сгенерировать и «отправить» одноразовую ссылку для входа.

        Всегда возвращает None (без ошибки), независимо от того, существует ли
        пользователь с таким email — защита от user enumeration.
        Вызывающий endpoint всегда отдаёт 202 Accepted.

        Если пользователь найден и активен:
        - Генерируется токен (secrets.token_urlsafe).
        - Payload ``{"email": ..., "user_id": ...}`` сохраняется в Redis
          с TTL 15 минут.
        - Отправка email будет реализована в Phase 6 (notifications / arq).
          В dev-окружении токен можно посмотреть через redis-cli:
          ``GET "magic:<token>"``.
        """
        email = email.strip().lower()

        # Проверка blocklist — молчаливо, не раскрываем блокировку
        if (
            self.email_blocklist_repo is not None
            and await self.email_blocklist_repo.is_blocked(email)
        ):
            return

        user = await self.user_repo.get_by_email(email)

        if user is None or not user.is_active:
            # Не раскрываем, существует ли пользователь
            return

        token = generate_token(self.TOKEN_LENGTH)

        payload = {
            "email": user.email,
            "user_id": str(user.id),
        }

        await self.redis.setex(
            f"magic:{token}",
            int(self.TOKEN_TTL.total_seconds()),
            json.dumps(payload),
        )

        # Аудит запроса magic-link
        if self.audit_service is not None:
            try:
                await self.audit_service.log_magic_link_requested(
                    user=user,
                )
            except Exception:
                import logging

                logging.getLogger(__name__).warning(
                    "Не удалось записать аудит magic-link request user=%s",
                    user.id,
                    exc_info=True,
                )

        # Отправка email с magic-link будет реализована в Phase 6
        # (notifications / arq). В dev-окружении ссылку можно посмотреть
        # в Redis: redis-cli GET "magic:<token>", либо через mailhog.

    # --- Верификация magic-link ---

    async def verify_magic_link(self, token: str) -> TokenPair:
        """Проверить одноразовый токен и выдать пару JWT.

        Токен удаляется из Redis атомарно (GETDEL) до выдачи JWT —
        даже при параллельных запросах второй получит ошибку.

        Raises:
            InvalidMagicLinkError: токен пуст, некорректной длины,
                не найден в Redis, содержит невалидный JSON/user_id,
                или пользователь не найден / деактивирован.
        """
        # 1. Проверка формата токена
        if not token:
            raise InvalidMagicLinkError()

        token_len = len(token)
        if token_len < self._MIN_TOKEN_LENGTH or token_len > self._MAX_TOKEN_LENGTH:
            raise InvalidMagicLinkError()

        # 2. Атомарное чтение + удаление из Redis (GETDEL — Redis 6.2+)
        raw = await self.redis.getdel(f"magic:{token}")
        if raw is None:
            raise InvalidMagicLinkError()

        # 3. Парсинг JSON
        try:
            payload: dict[str, str] = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as exc:
            raise InvalidMagicLinkError() from exc

        # 4. Извлечение и валидация полей
        email: str | None = payload.get("email")
        user_id_raw: str | None = payload.get("user_id")

        if not email or not user_id_raw:
            raise InvalidMagicLinkError()

        try:
            user_id = UUID(user_id_raw)
        except ValueError as exc:
            raise InvalidMagicLinkError() from exc

        # 5. Загрузка пользователя
        user = await self.user_repo.get_by_id(user_id)
        if user is None or not user.is_active:
            raise InvalidMagicLinkError()

        # 5a. Проверка статуса организации для organizer'ов
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

        # 6. Обновление last_login
        await self.user_repo.update_last_login(user)

        # 7. Выдача токенов
        tokens = self.auth_service.issue_tokens(user)

        # Аудит верификации magic-link
        if self.audit_service is not None:
            try:
                await self.audit_service.log_magic_link_verified(
                    user=user,
                )
            except Exception:
                import logging

                logging.getLogger(__name__).warning(
                    "Не удалось записать аудит magic-link verify user=%s",
                    user.id,
                    exc_info=True,
                )

        return tokens
