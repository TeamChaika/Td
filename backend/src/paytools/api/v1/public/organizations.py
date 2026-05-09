"""POST /organizations/register — регистрация новой организации и первого организатора.
   GET /organizations/slug-check — проверка доступности slug.

Публичные эндпоинты без авторизации. Создаёт организацию в статусе
PENDING_MODERATION и учётную запись организатора с ролью ORGANIZER.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from paytools.api.v1.deps import SessionDep
from paytools.api.v1.schemas.auth import (
    OrganizationRegisterRequest,
    RegisterResponse,
)
from paytools.core.redis import get_redis_client
from paytools.db.repositories.audit import AuditLogRepository
from paytools.db.repositories.email_blocklist import EmailBlocklistRepository
from paytools.db.repositories.organization import OrganizationRepository
from paytools.db.repositories.user import UserRepository
from paytools.domain.audit.service import AuditService
from paytools.domain.auth.service import AuthService, SignupInput
from paytools.domain.organizations.service import OrganizationService
from paytools.domain.organizations.validation import SlugValidationError, validate_slug

router = APIRouter()


@router.get(
    "/organizations/slug-check",
    summary="Проверка доступности slug",
    description=(
        "Проверяет, доступен ли slug для регистрации. Возвращает "
        "available=true/false и причину, если занят или невалиден."
    ),
    responses={200: {"description": "Результат проверки"}},
)
async def slug_check(
    slug: Annotated[
        str, Query(min_length=1, max_length=64, description="Slug для проверки")
    ],
    session: SessionDep,
) -> dict[str, bool | str | None]:
    """Проверить доступность slug организации.

    Возможные ответы:
    - {"available": true, "reason": null} — slug свободен
    - {"available": false, "reason": "taken"} — slug уже занят
    - {"available": false, "reason": "reserved"} — slug зарезервирован
    - {"available": false, "reason": "invalid_format"} — slug не соответствует формату
    """
    # Нормализация
    normalized = slug.strip().lower()

    # Проверка формата и зарезервированных
    try:
        validate_slug(normalized)
    except SlugValidationError as err:
        reason: str
        match err.code:
            case "reserved":
                reason = "reserved"
            case _:
                reason = "invalid_format"
        return {"available": False, "reason": reason}

    # Проверка занятости
    org_repo = OrganizationRepository(session)
    if await org_repo.slug_exists(normalized):
        return {"available": False, "reason": "taken"}

    return {"available": True, "reason": None}


@router.post(
    "/organizations/register",
    response_model=RegisterResponse,
    status_code=201,
    summary="Регистрация организации",
    description=(
        "Создаёт новую организацию со статусом pending_moderation "
        "и первого пользователя-организатора."
    ),
    responses={
        201: {"description": "Организация создана"},
        400: {"description": "Слабый пароль или невалидный slug"},
        409: {"description": "Email или slug уже заняты"},
    },
)
async def register_organization(
    data: OrganizationRegisterRequest,
    session: SessionDep,
) -> RegisterResponse:
    """Зарегистрировать организацию с первым пользователем-организатором.

    Организация создаётся в статусе PENDING_MODERATION. Логин невозможен
    до одобрения суперадмином — токены не выдаём. Доменные ошибки
    (PasswordTooWeakError, SlugInvalidError, SlugTakenError, EmailTakenError)
    мапятся автоматически через глобальный domain_error_handler.
    """
    user_repo = UserRepository(session)
    org_repo = OrganizationRepository(session)
    audit_repo = AuditLogRepository(session, organization_id=None)
    audit_service_inst = AuditService(session, repo=audit_repo)
    redis = get_redis_client()
    email_blocklist_repo = EmailBlocklistRepository(session)
    org_service = OrganizationService(
        session,
        org_repo=org_repo,
        user_repo=user_repo,
        audit_service=audit_service_inst,
        redis=redis,
    )
    auth_service = AuthService(
        session,
        user_repo=user_repo,
        org_service=org_service,
        redis=redis,
        email_blocklist_repo=email_blocklist_repo,
        org_repo=org_repo,
    )

    signup_input = SignupInput(
        email=data.email,
        password=data.password,
        first_name=data.first_name,
        last_name=data.last_name,
        organization_name=data.organization_name,
        organization_slug=data.organization_slug,
    )

    organization, user = await auth_service.signup_organization(signup_input)

    return RegisterResponse.model_validate(
        {
            "organization_id": organization.id,
            "user_id": user.id,
            "status": organization.status,
        }
    )
