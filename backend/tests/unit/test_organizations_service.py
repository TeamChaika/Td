"""Unit-тесты OrganizationService: регистрация, настройки, маскирование QRM."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
import sqlalchemy.exc
from sqlalchemy.ext.asyncio import AsyncSession

from paytools.core.errors import ForbiddenError, NotFoundError
from paytools.core.security import encrypt_secret
from paytools.db.models.enums import OrganizationStatus, UserRole
from paytools.db.models.organization import Organization
from paytools.db.models.user import User
from paytools.db.repositories.organization import OrganizationRepository
from paytools.db.repositories.user import UserRepository
from paytools.domain.organizations.service import (
    UNSET,
    EmailTakenError,
    OrganizationService,
    RegisterOrganizationInput,
    SlugTakenError,
    UpdateSettingsInput,
)


def _make_org(
    org_id: UUID | None = None,
    slug: str = "test-org",
    name: str = "Test Org",
    status: OrganizationStatus = OrganizationStatus.PENDING_MODERATION,
) -> Organization:
    """Создать тестовую модель Organization."""
    org = Organization(
        id=org_id or uuid4(),
        slug=slug,
        name=name,
        status=status,
    )
    return org


def _make_user(
    user_id: UUID | None = None,
    email: str = "test@example.com",
    role: UserRole = UserRole.ORGANIZER,
    org_id: UUID | None = None,
) -> User:
    """Создать тестовую модель User."""
    return User(
        id=user_id or uuid4(),
        email=email,
        password_hash="hashed",
        first_name="Test",
        last_name="User",
        role=role,
        is_active=True,
        organization_id=org_id,
    )


class TestOrganizationServiceRegister:
    """Тесты метода register."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def mock_org_repo(self) -> AsyncMock:
        repo = AsyncMock(spec=OrganizationRepository)
        repo.slug_exists.return_value = False
        return repo

    @pytest.fixture
    def mock_user_repo(self) -> AsyncMock:
        repo = AsyncMock(spec=UserRepository)
        repo.email_exists.return_value = False
        return repo

    @pytest.fixture
    def service(
        self,
        mock_session: AsyncMock,
        mock_org_repo: AsyncMock,
        mock_user_repo: AsyncMock,
    ) -> OrganizationService:
        return OrganizationService(
            mock_session,
            org_repo=mock_org_repo,
            user_repo=mock_user_repo,
        )

    @pytest.fixture
    def valid_input(self) -> RegisterOrganizationInput:
        return RegisterOrganizationInput(
            email="test@example.com",
            password_hash="hashed_password",
            first_name="Test",
            last_name="User",
            organization_name="Test Org",
            organization_slug="test-org",
        )

    async def test_creates_org_and_user_atomically(
        self,
        service: OrganizationService,
        mock_org_repo: AsyncMock,
        mock_user_repo: AsyncMock,
        valid_input: RegisterOrganizationInput,
    ) -> None:
        """Успешная регистрация создаёт организацию и пользователя."""
        org = _make_org()
        user = _make_user(org_id=org.id)
        mock_org_repo.create.return_value = org
        mock_user_repo.create.return_value = user

        result_org, result_user = await service.register(valid_input)

        assert result_org == org
        assert result_user == user
        mock_org_repo.create.assert_called_once_with(
            slug="test-org",
            name="Test Org",
            status=OrganizationStatus.PENDING_MODERATION,
        )
        mock_user_repo.create.assert_called_once()
        # Проверяем что flush был вызван
        service.session.flush.assert_called_once()  # type: ignore[union-attr]

    async def test_slug_taken_raises(
        self,
        service: OrganizationService,
        mock_org_repo: AsyncMock,
        valid_input: RegisterOrganizationInput,
    ) -> None:
        """Если slug занят — SlugTakenError."""
        mock_org_repo.slug_exists.return_value = True

        with pytest.raises(SlugTakenError):
            await service.register(valid_input)

    async def test_email_taken_raises(
        self,
        service: OrganizationService,
        mock_user_repo: AsyncMock,
        valid_input: RegisterOrganizationInput,
    ) -> None:
        """Если email занят — EmailTakenError."""
        mock_user_repo.email_exists.return_value = True

        with pytest.raises(EmailTakenError):
            await service.register(valid_input)

    async def test_integrity_error_maps_to_slug_taken(
        self,
        service: OrganizationService,
        mock_org_repo: AsyncMock,
        mock_user_repo: AsyncMock,
        valid_input: RegisterOrganizationInput,
    ) -> None:
        """IntegrityError с constraint slug мапится в SlugTakenError."""
        # Создаём IntegrityError с orig, у которого есть constraint_name
        pg_error = Exception("duplicate key value violates unique constraint")
        pg_error.constraint_name = "organizations_slug_key"
        mock_org_repo.create.side_effect = sqlalchemy.exc.IntegrityError(
            "statement",
            {"constraint_name": "organizations_slug_key"},
            orig=pg_error,
        )

        with pytest.raises(SlugTakenError):
            await service.register(valid_input)

    async def test_integrity_error_maps_to_email_taken(
        self,
        service: OrganizationService,
        mock_org_repo: AsyncMock,
        mock_user_repo: AsyncMock,
        valid_input: RegisterOrganizationInput,
    ) -> None:
        """IntegrityError с constraint email мапится в EmailTakenError."""
        org = _make_org()
        mock_org_repo.create.return_value = org
        pg_error = Exception("duplicate key value violates unique constraint")
        pg_error.constraint_name = "users_email_key"
        mock_user_repo.create.side_effect = sqlalchemy.exc.IntegrityError(
            "statement",
            {"constraint_name": "users_email_key"},
            orig=pg_error,
        )

        with pytest.raises(EmailTakenError):
            await service.register(valid_input)

    async def test_assert_lowercase_slug(
        self,
        service: OrganizationService,
        mock_org_repo: AsyncMock,
        mock_user_repo: AsyncMock,
    ) -> None:
        """Slug с заглавными буквами вызывает ValueError."""
        input_data = RegisterOrganizationInput(
            email="test@example.com",
            password_hash="hashed",
            first_name="Test",
            last_name="User",
            organization_name="Test Org",
            organization_slug="Test-Org",  # Заглавные буквы
        )

        with pytest.raises(ValueError, match="нижнем регистре"):
            await service.register(input_data)


class TestOrganizationServiceUpdateSettings:
    """Тесты метода update_settings."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def mock_org_repo(self) -> AsyncMock:
        repo = AsyncMock(spec=OrganizationRepository)
        return repo

    @pytest.fixture
    def mock_user_repo(self) -> AsyncMock:
        return AsyncMock(spec=UserRepository)

    @pytest.fixture
    def service(
        self,
        mock_session: AsyncMock,
        mock_org_repo: AsyncMock,
        mock_user_repo: AsyncMock,
    ) -> OrganizationService:
        return OrganizationService(
            mock_session,
            org_repo=mock_org_repo,
            user_repo=mock_user_repo,
        )

    @pytest.fixture
    def existing_org(self) -> Organization:
        return _make_org(
            slug="test-org",
            name="Test Org",
            status=OrganizationStatus.ACTIVE,
        )

    async def test_unset_fields_not_overwritten(
        self,
        service: OrganizationService,
        mock_org_repo: AsyncMock,
        existing_org: Organization,
    ) -> None:
        """Поля UNSET не перезаписываются."""
        mock_org_repo.get_by_id.return_value = existing_org
        original_brand_name = existing_org.brand_name

        data = UpdateSettingsInput(
            brand_name=UNSET,
            brand_color=UNSET,
            logo_url=UNSET,
            qrm_api_key_plain=UNSET,
        )

        result = await service.update_settings(existing_org.id, data)

        assert result.brand_name == original_brand_name

    async def test_brand_name_updates(
        self,
        service: OrganizationService,
        mock_org_repo: AsyncMock,
        existing_org: Organization,
    ) -> None:
        """brand_name обновляется."""
        mock_org_repo.get_by_id.return_value = existing_org

        data = UpdateSettingsInput(brand_name="New Brand")
        result = await service.update_settings(existing_org.id, data)

        assert result.brand_name == "New Brand"

    async def test_brand_color_updates(
        self,
        service: OrganizationService,
        mock_org_repo: AsyncMock,
        existing_org: Organization,
    ) -> None:
        """brand_color обновляется."""
        mock_org_repo.get_by_id.return_value = existing_org

        data = UpdateSettingsInput(brand_color="#FF5500")
        result = await service.update_settings(existing_org.id, data)

        assert result.brand_color == "#FF5500"

    async def test_brand_color_none_clears(
        self,
        service: OrganizationService,
        mock_org_repo: AsyncMock,
        existing_org: Organization,
    ) -> None:
        """brand_color=None очищает поле."""
        existing_org.brand_color = "#FF5500"
        mock_org_repo.get_by_id.return_value = existing_org

        data = UpdateSettingsInput(brand_color=None)
        result = await service.update_settings(existing_org.id, data)

        assert result.brand_color is None

    async def test_qrm_api_key_encrypted(
        self,
        service: OrganizationService,
        mock_org_repo: AsyncMock,
        existing_org: Organization,
    ) -> None:
        """qrm_api_key_plain шифруется при сохранении."""
        mock_org_repo.get_by_id.return_value = existing_org

        data = UpdateSettingsInput(qrm_api_key_plain="sk_live_test_key_12345")
        result = await service.update_settings(existing_org.id, data)

        # В БД должен быть зашифрованный ключ, не plaintext
        assert result.qrm_api_key_encrypted is not None
        assert result.qrm_api_key_encrypted != "sk_live_test_key_12345"
        assert "sk_live_test_key_12345" not in (result.qrm_api_key_encrypted or "")

    async def test_qrm_api_key_empty_clears(
        self,
        service: OrganizationService,
        mock_org_repo: AsyncMock,
        existing_org: Organization,
    ) -> None:
        """Пустая строка qrm_api_key_plain очищает ключ."""
        existing_org.qrm_api_key_encrypted = encrypt_secret("old-key")
        mock_org_repo.get_by_id.return_value = existing_org

        data = UpdateSettingsInput(qrm_api_key_plain="")
        result = await service.update_settings(existing_org.id, data)

        assert result.qrm_api_key_encrypted is None

    async def test_contact_email_updates(
        self,
        service: OrganizationService,
        mock_org_repo: AsyncMock,
        existing_org: Organization,
    ) -> None:
        """contact_email обновляется."""
        mock_org_repo.get_by_id.return_value = existing_org

        data = UpdateSettingsInput(contact_email="info@example.com")
        result = await service.update_settings(existing_org.id, data)

        assert result.contact_email == "info@example.com"

    async def test_legal_inn_updates(
        self,
        service: OrganizationService,
        mock_org_repo: AsyncMock,
        existing_org: Organization,
    ) -> None:
        """legal_inn обновляется."""
        mock_org_repo.get_by_id.return_value = existing_org

        data = UpdateSettingsInput(legal_inn="1234567890")
        result = await service.update_settings(existing_org.id, data)

        assert result.legal_inn == "1234567890"

    async def test_telegram_chat_id_updates(
        self,
        service: OrganizationService,
        mock_org_repo: AsyncMock,
        existing_org: Organization,
    ) -> None:
        """telegram_chat_id обновляется."""
        mock_org_repo.get_by_id.return_value = existing_org

        data = UpdateSettingsInput(telegram_chat_id=-1001234567890)
        result = await service.update_settings(existing_org.id, data)

        assert result.telegram_chat_id == -1001234567890

    async def test_qrm_api_login_updates(
        self,
        service: OrganizationService,
        mock_org_repo: AsyncMock,
        existing_org: Organization,
    ) -> None:
        """qrm_api_login обновляется."""
        mock_org_repo.get_by_id.return_value = existing_org

        data = UpdateSettingsInput(qrm_api_login="my_qrm_login")
        result = await service.update_settings(existing_org.id, data)

        assert result.qrm_api_login == "my_qrm_login"

    async def test_refund_policy_updates(
        self,
        service: OrganizationService,
        mock_org_repo: AsyncMock,
        existing_org: Organization,
    ) -> None:
        """refund_policy обновляется."""
        mock_org_repo.get_by_id.return_value = existing_org

        data = UpdateSettingsInput(refund_policy="Возврат в течение 7 дней")
        result = await service.update_settings(existing_org.id, data)

        assert result.refund_policy == "Возврат в течение 7 дней"

    async def test_timezone_updates(
        self,
        service: OrganizationService,
        mock_org_repo: AsyncMock,
        existing_org: Organization,
    ) -> None:
        """timezone обновляется."""
        mock_org_repo.get_by_id.return_value = existing_org

        data = UpdateSettingsInput(timezone="Asia/Yekaterinburg")
        result = await service.update_settings(existing_org.id, data)

        assert result.timezone == "Asia/Yekaterinburg"

    async def test_legal_entity_type_updates(
        self,
        service: OrganizationService,
        mock_org_repo: AsyncMock,
        existing_org: Organization,
    ) -> None:
        """legal_entity_type обновляется."""
        mock_org_repo.get_by_id.return_value = existing_org

        from paytools.db.models.enums import LegalEntityType

        data = UpdateSettingsInput(legal_entity_type=LegalEntityType.OOO)
        result = await service.update_settings(existing_org.id, data)

        assert result.legal_entity_type == LegalEntityType.OOO

    async def test_qrm_prod_mode_updates(
        self,
        service: OrganizationService,
        mock_org_repo: AsyncMock,
        existing_org: Organization,
    ) -> None:
        """qrm_prod_mode обновляется."""
        mock_org_repo.get_by_id.return_value = existing_org

        data = UpdateSettingsInput(qrm_prod_mode=True)
        result = await service.update_settings(existing_org.id, data)

        assert result.qrm_prod_mode is True


class TestMaskQrmKey:
    """Тесты mask_qrm_key."""

    @pytest.fixture
    def service(self) -> OrganizationService:
        """Сервис без зависимостей (mask_qrm_key — синхронный)."""
        return OrganizationService(
            AsyncMock(spec=AsyncSession),
            org_repo=AsyncMock(spec=OrganizationRepository),
            user_repo=AsyncMock(spec=UserRepository),
        )

    def test_returns_masked_key(self, service: OrganizationService) -> None:
        """Ключ маскируется: **** + последние 4 символа."""
        encrypted = encrypt_secret("sk_live_my_secret_key_abcd1234")
        masked = service.mask_qrm_key(encrypted)
        assert masked is not None
        assert masked.startswith("****")
        assert masked.endswith("1234")

    def test_none_returns_none(self, service: OrganizationService) -> None:
        """None возвращает None."""
        assert service.mask_qrm_key(None) is None

    def test_empty_string_returns_none(self, service: OrganizationService) -> None:
        """Пустая строка возвращает None."""
        assert service.mask_qrm_key("") is None

    def test_short_key_returns_stars(self, service: OrganizationService) -> None:
        """Короткий ключ (< 4 символов) возвращает '****'."""
        encrypted = encrypt_secret("ab")
        masked = service.mask_qrm_key(encrypted)
        assert masked == "****"

    def test_invalid_encrypted_returns_stars(
        self, service: OrganizationService
    ) -> None:
        """Некорректный шифротекст возвращает '****'."""
        masked = service.mask_qrm_key("not-valid-fernet-data")
        assert masked == "****"


class TestOrganizationServiceApproveSuspend:
    """Тесты approve и suspend."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def mock_org_repo(self) -> AsyncMock:
        return AsyncMock(spec=OrganizationRepository)

    @pytest.fixture
    def mock_user_repo(self) -> AsyncMock:
        return AsyncMock(spec=UserRepository)

    @pytest.fixture
    def service(
        self,
        mock_session: AsyncMock,
        mock_org_repo: AsyncMock,
        mock_user_repo: AsyncMock,
    ) -> OrganizationService:
        return OrganizationService(
            mock_session,
            org_repo=mock_org_repo,
            user_repo=mock_user_repo,
        )

    async def test_approve_already_active_is_idempotent(
        self,
        service: OrganizationService,
        mock_org_repo: AsyncMock,
    ) -> None:
        """Одобрение уже ACTIVE организации идемпотентно."""
        org = _make_org(status=OrganizationStatus.ACTIVE)
        mock_org_repo.get_by_id.return_value = org
        admin = _make_user(role=UserRole.SUPERADMIN)

        result = await service.approve(org.id, by_user=admin)

        assert result == org
        mock_org_repo.set_status.assert_not_called()

    async def test_approve_by_non_superadmin_raises(
        self,
        service: OrganizationService,
        mock_org_repo: AsyncMock,
    ) -> None:
        """Не-superadmin не может одобрить."""
        org = _make_org()
        mock_org_repo.get_by_id.return_value = org
        organizer = _make_user(role=UserRole.ORGANIZER)

        with pytest.raises(ForbiddenError):
            await service.approve(org.id, by_user=organizer)

    async def test_suspend_already_suspended_is_idempotent(
        self,
        service: OrganizationService,
        mock_org_repo: AsyncMock,
    ) -> None:
        """Suspend уже SUSPENDED организации идемпотентен."""
        org = _make_org(status=OrganizationStatus.SUSPENDED)
        mock_org_repo.get_by_id.return_value = org
        admin = _make_user(role=UserRole.SUPERADMIN)

        result = await service.suspend(org.id, by_user=admin, reason="test")

        assert result == org
        mock_org_repo.set_status.assert_not_called()

    async def test_suspend_empty_reason_raises(
        self,
        service: OrganizationService,
        mock_org_repo: AsyncMock,
    ) -> None:
        """Пустой reason вызывает ValueError."""
        org = _make_org()
        mock_org_repo.get_by_id.return_value = org
        admin = _make_user(role=UserRole.SUPERADMIN)

        with pytest.raises(ValueError):
            await service.suspend(org.id, by_user=admin, reason="   ")


class TestOrganizationServiceGetBy:
    """Тесты get_by_slug и get_by_id."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def mock_org_repo(self) -> AsyncMock:
        return AsyncMock(spec=OrganizationRepository)

    @pytest.fixture
    def mock_user_repo(self) -> AsyncMock:
        return AsyncMock(spec=UserRepository)

    @pytest.fixture
    def service(
        self,
        mock_session: AsyncMock,
        mock_org_repo: AsyncMock,
        mock_user_repo: AsyncMock,
    ) -> OrganizationService:
        return OrganizationService(
            mock_session,
            org_repo=mock_org_repo,
            user_repo=mock_user_repo,
        )

    async def test_get_by_slug_not_found_raises(
        self,
        service: OrganizationService,
        mock_org_repo: AsyncMock,
    ) -> None:
        """Ненайденный slug вызывает NotFoundError."""
        mock_org_repo.get_by_slug.return_value = None

        with pytest.raises(NotFoundError):
            await service.get_by_slug("nonexistent")

    async def test_get_by_id_not_found_raises(
        self,
        service: OrganizationService,
        mock_org_repo: AsyncMock,
    ) -> None:
        """Ненайденный id вызывает NotFoundError."""
        mock_org_repo.get_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await service.get_by_id(uuid4())
