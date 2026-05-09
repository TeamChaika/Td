"""Эндпоинты организатора: управление своей организацией.

GET    /organizer/organization      — получить настройки
PATCH  /organizer/organization      — обновить настройки
POST   /organizer/organization/qrm/test — проверить QRM-ключ
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from paytools.api.v1.deps import OrganizerUser, SessionDep
from paytools.api.v1.schemas.organizations import (
    OrganizationRead,
    OrganizationUpdateRequest,
    QRMTestRequest,
    QRMTestResponse,
)
from paytools.core.config import get_settings
from paytools.core.errors import OrganizationRequiredError
from paytools.core.redis import get_redis_client
from paytools.core.security import decrypt_secret
from paytools.db.models.organization import Organization
from paytools.db.repositories.audit import AuditLogRepository
from paytools.db.repositories.organization import OrganizationRepository
from paytools.db.repositories.user import UserRepository
from paytools.domain.audit.service import AuditService
from paytools.domain.organizations.service import (
    UNSET,
    OrganizationService,
    UpdateSettingsInput,
)

router = APIRouter()


def _build_org_service(session: AsyncSession) -> OrganizationService:
    """Собрать OrganizationService с нужными репозиториями и аудитом."""
    user_repo = UserRepository(session)
    org_repo = OrganizationRepository(session)
    audit_repo = AuditLogRepository(session, organization_id=None)
    audit_service = AuditService(session, repo=audit_repo)
    redis = get_redis_client()
    return OrganizationService(
        session,
        org_repo=org_repo,
        user_repo=user_repo,
        audit_service=audit_service,
        redis=redis,
    )


def _to_read_response(org: Organization, svc: OrganizationService) -> OrganizationRead:
    """Смаппить модель Organization в ответ OrganizationRead.

    qrm_api_key_masked — вычисляемое поле, отсутствует в SQLAlchemy-модели,
    поэтому после model_validate проставляем его через маскирование.
    """
    payload = OrganizationRead.model_validate(org)
    payload.qrm_api_key_masked = svc.mask_qrm_key(org.qrm_api_key_encrypted)
    return payload


@router.get(
    "",
    response_model=OrganizationRead,
    summary="Моя организация",
    description="Полные настройки организации текущего организатора.",
)
async def get_my_organization(
    user: OrganizerUser,
    session: SessionDep,
) -> OrganizationRead:
    """Получить настройки организации текущего организатора.

    Tenant isolation: organization_id берётся исключительно из JWT (через
    OrganizerUser), а не из query/body. Организатор не может прочитать
    чужую организацию, даже если попытается подменить параметры запроса.
    """
    if user.organization_id is None:
        raise OrganizationRequiredError(
            details={"user_id": str(user.id)},
        )
    svc = _build_org_service(session)
    org = await svc.get_by_id(user.organization_id)
    return _to_read_response(org, svc)


@router.patch(
    "",
    response_model=OrganizationRead,
    summary="Обновить настройки организации",
)
async def update_my_organization(
    data: OrganizationUpdateRequest,
    user: OrganizerUser,
    session: SessionDep,
) -> OrganizationRead:
    """Обновить настройки организации (PATCH-семантика).

    Обновляются только переданные поля. qrm_api_key при сохранении шифруется.
    """
    if user.organization_id is None:
        raise OrganizationRequiredError(
            details={"user_id": str(user.id)},
        )

    # Конвертация Pydantic-схемы → доменный DTO (PATCH-семантика)
    pydantic_updates = data.model_dump(exclude_unset=True)
    qrm_key = pydantic_updates.pop("qrm_api_key", UNSET)
    settings_input = UpdateSettingsInput(
        brand_name=pydantic_updates.get("brand_name", UNSET),
        logo_url=pydantic_updates.get("logo_url", UNSET),
        brand_color=pydantic_updates.get("brand_color", UNSET),
        contact_email=pydantic_updates.get("contact_email", UNSET),
        contact_phone=pydantic_updates.get("contact_phone", UNSET),
        legal_entity_type=pydantic_updates.get("legal_entity_type", UNSET),
        legal_inn=pydantic_updates.get("legal_inn", UNSET),
        legal_name=pydantic_updates.get("legal_name", UNSET),
        legal_address=pydantic_updates.get("legal_address", UNSET),
        qrm_api_login=pydantic_updates.get("qrm_api_login", UNSET),
        qrm_prod_mode=pydantic_updates.get("qrm_prod_mode", UNSET),
        telegram_chat_id=pydantic_updates.get("telegram_chat_id", UNSET),
        refund_policy=pydantic_updates.get("refund_policy", UNSET),
        timezone=pydantic_updates.get("timezone", UNSET),
        qrm_api_key_plain=qrm_key if qrm_key is not UNSET else UNSET,
    )

    svc = _build_org_service(session)
    org = await svc.update_settings(user.organization_id, settings_input, by_user=user)
    return _to_read_response(org, svc)


@router.post(
    "/qrm/test",
    response_model=QRMTestResponse,
    summary="Проверить QRM-ключ",
    description=(
        "Вызывает QRM /users/check-api-key/ — с переданным ключом "
        "или с уже сохранённым."
    ),
)
async def test_qrm_key(
    data: QRMTestRequest,
    user: OrganizerUser,
    session: SessionDep,
) -> QRMTestResponse:
    """Проверить QRM-ключ: переданный ad-hoc или сохранённый в организации.

    Если ключ не передан в теле запроса и не сохранён в организации — вернёт
    ok=False с сообщением, а не ошибку.
    """
    if user.organization_id is None:
        raise OrganizationRequiredError(
            details={"user_id": str(user.id)},
        )

    # Определяем API-ключ: явно переданный или сохранённый
    if data.qrm_api_key:
        api_key = data.qrm_api_key
    else:
        svc = _build_org_service(session)
        org = await svc.get_by_id(user.organization_id)
        if not org.qrm_api_key_encrypted:
            return QRMTestResponse(
                ok=False,
                message="QRM-ключ не задан",
                details=None,
            )
        try:
            api_key = decrypt_secret(org.qrm_api_key_encrypted)
        except ValueError:
            return QRMTestResponse(
                ok=False,
                message="Не удалось расшифровать сохранённый QRM-ключ",
                details=None,
            )

    # Вызываем QRM /users/check-api-key/
    settings = get_settings()
    qrm_url = f"{settings.qrm_base_url.rstrip('/')}/users/check-api-key/"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(qrm_url, headers={"X-Api-Key": api_key})
        if resp.status_code == 200:
            body = resp.json()
            return QRMTestResponse(ok=True, message="Ключ валиден", details=body)
        return QRMTestResponse(
            ok=False,
            message=f"QRM вернул {resp.status_code}",
            details={
                "status_code": resp.status_code,
                # Только первые 500 символов — не храним полный ответ,
                # чтобы не утекли данные аккаунта QRM.
                "body": resp.text[:500],
            },
        )
    except httpx.HTTPError as e:
        return QRMTestResponse(
            ok=False,
            message=f"Ошибка связи с QRM: {e.__class__.__name__}",
            details=None,
        )
