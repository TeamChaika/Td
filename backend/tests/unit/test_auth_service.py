"""Unit-тесты AuthService: signup, login, refresh, logout."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from paytools.core.config import Settings
from paytools.core.errors import AuthError, OrganizationSuspendedError
from paytools.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
)
from paytools.db.models.enums import OrganizationStatus, UserRole
from paytools.db.models.organization import Organization
from paytools.db.models.user import User
from paytools.db.repositories.user import UserRepository
from paytools.domain.auth.errors import (
    EmailBlockedError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    OrganizationPendingError,
    PasswordTooWeakError,
    SlugInvalidError,
)
from paytools.domain.auth.service import AuthService, SignupInput, TokenPair
from paytools.domain.organizations.service import OrganizationService


def _make_user(
    user_id: UUID | None = None,
    email: str = "test@example.com",
    role: UserRole = UserRole.ORGANIZER,
    org_id: UUID | None = None,
    password_hash: str | None = None,
    is_active: bool = True,
) -> User:
    """Создать тестовую модель User."""
    return User(
        id=user_id or uuid4(),
        email=email,
        password_hash=password_hash or hash_password("TestPass123!"),
        first_name="Test",
        last_name="User",
        role=role,
        is_active=is_active,
        organization_id=org_id,
    )


def _make_org(
    org_id: UUID | None = None,
    slug: str = "test-org",
    status: OrganizationStatus = OrganizationStatus.ACTIVE,
) -> Organization:
    """Создать тестовую модель Organization."""
    return Organization(
        id=org_id or uuid4(),
        slug=slug,
        name="Test Org",
        status=status,
    )


def _build_test_settings() -> Settings:
    return Settings(
        env="test",
        database_url="postgresql+asyncpg://tdpay:tdpay@localhost:5432/tdpay_test",
        redis_url="redis://localhost:6379/0",
        secret_key="test-secret-key-at-least-32-chars!!",
        fernet_key="DoS7l0dqk2ewkyuqDsLLWpTi1i2FWzA_AZAjjuHQXKg=",
        jwt_secret="test-jwt-secret-at-least-32-chars!!",
        jwt_access_ttl_min=15,
        jwt_refresh_ttl_days=30,
        s3_endpoint="http://localhost:9000",
        s3_bucket="tdpay-test",
        s3_access_key="minioadmin",
        s3_secret_key="minioadmin",
        s3_region="ru-1",
        smtp_host="localhost",
        smtp_port=1025,
        smtp_from="test@tdpay.local",
        platform_domain="tdpay.local",
        platform_url="http://localhost:3000",
    )


class TestAuthServiceSignup:
    """Тесты signup_organization."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def mock_user_repo(self) -> AsyncMock:
        return AsyncMock(spec=UserRepository)

    @pytest.fixture
    def mock_org_service(self) -> AsyncMock:
        return AsyncMock(spec=OrganizationService)

    @pytest.fixture
    def mock_redis(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def mock_email_blocklist(self) -> AsyncMock:
        repo = AsyncMock()
        repo.is_blocked.return_value = False
        return repo

    @pytest.fixture
    def mock_org_repo(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def test_settings(self) -> Settings:
        return _build_test_settings()

    @pytest.fixture
    def service(
        self,
        mock_session: AsyncMock,
        mock_user_repo: AsyncMock,
        mock_org_service: AsyncMock,
        mock_redis: AsyncMock,
        mock_email_blocklist: AsyncMock,
        mock_org_repo: AsyncMock,
        test_settings: Settings,
    ) -> AuthService:
        with patch(
            "paytools.domain.auth.service.get_settings",
            return_value=test_settings,
        ):
            return AuthService(
                mock_session,
                user_repo=mock_user_repo,
                org_service=mock_org_service,
                redis=mock_redis,
                email_blocklist_repo=mock_email_blocklist,
                org_repo=mock_org_repo,
            )

    @pytest.fixture
    def valid_input(self) -> SignupInput:
        return SignupInput(
            email="test@example.com",
            password="StrongPass123!",
            first_name="Test",
            last_name="User",
            organization_name="Test Org",
            organization_slug="test-org",
        )

    async def test_successful_signup(
        self,
        service: AuthService,
        mock_org_service: AsyncMock,
        valid_input: SignupInput,
    ) -> None:
        """Успешная регистрация возвращает org + user."""
        org = _make_org()
        user = _make_user(org_id=org.id)
        mock_org_service.register.return_value = (org, user)

        result_org, result_user = await service.signup_organization(valid_input)

        assert result_org == org
        assert result_user == user
        mock_org_service.register.assert_called_once()

    async def test_weak_password_raises(
        self,
        service: AuthService,
        valid_input: SignupInput,
    ) -> None:
        """Пароль короче 10 символов вызывает PasswordTooWeakError."""
        valid_input.password = "short"

        with pytest.raises(PasswordTooWeakError):
            await service.signup_organization(valid_input)

    async def test_invalid_slug_raises(
        self,
        service: AuthService,
        valid_input: SignupInput,
    ) -> None:
        """Невалидный slug вызывает SlugInvalidError."""
        valid_input.organization_slug = "AB"  # too short

        with pytest.raises(SlugInvalidError):
            await service.signup_organization(valid_input)

    async def test_reserved_slug_raises(
        self,
        service: AuthService,
        valid_input: SignupInput,
    ) -> None:
        """Зарезервированный slug вызывает SlugInvalidError."""
        valid_input.organization_slug = "admin"

        with pytest.raises(SlugInvalidError):
            await service.signup_organization(valid_input)

    async def test_email_blocked_raises(
        self,
        service: AuthService,
        mock_email_blocklist: AsyncMock,
        valid_input: SignupInput,
    ) -> None:
        """Email в блоклисте вызывает EmailBlockedError."""
        mock_email_blocklist.is_blocked.return_value = True

        with pytest.raises(EmailBlockedError):
            await service.signup_organization(valid_input)

    async def test_email_normalized_to_lowercase(
        self,
        service: AuthService,
        mock_org_service: AsyncMock,
        valid_input: SignupInput,
    ) -> None:
        """Email приводится к нижнему регистру."""
        valid_input.email = "Test@Example.COM"
        org = _make_org()
        user = _make_user(org_id=org.id)
        mock_org_service.register.return_value = (org, user)

        await service.signup_organization(valid_input)

        call_args = mock_org_service.register.call_args[0][0]
        assert call_args.email == "test@example.com"


class TestAuthServiceLogin:
    """Тесты login."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def mock_user_repo(self) -> AsyncMock:
        return AsyncMock(spec=UserRepository)

    @pytest.fixture
    def mock_org_service(self) -> AsyncMock:
        return AsyncMock(spec=OrganizationService)

    @pytest.fixture
    def mock_redis(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def mock_org_repo(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def test_settings(self) -> Settings:
        return _build_test_settings()

    @pytest.fixture
    def service(
        self,
        mock_session: AsyncMock,
        mock_user_repo: AsyncMock,
        mock_org_service: AsyncMock,
        mock_redis: AsyncMock,
        mock_org_repo: AsyncMock,
        test_settings: Settings,
    ) -> AuthService:
        with patch(
            "paytools.domain.auth.service.get_settings",
            return_value=test_settings,
        ):
            return AuthService(
                mock_session,
                user_repo=mock_user_repo,
                org_service=mock_org_service,
                redis=mock_redis,
                org_repo=mock_org_repo,
            )

    async def test_successful_login(
        self,
        service: AuthService,
        mock_user_repo: AsyncMock,
        mock_org_repo: AsyncMock,
    ) -> None:
        """Успешный логин возвращает TokenPair."""
        org = _make_org(status=OrganizationStatus.ACTIVE)
        user = _make_user(
            email="test@example.com",
            password_hash=hash_password("TestPass123!"),
            org_id=org.id,
        )
        mock_user_repo.get_by_email.return_value = user
        mock_org_repo.get_by_id.return_value = org

        tokens = await service.login("test@example.com", "TestPass123!")

        assert isinstance(tokens, TokenPair)
        assert tokens.access_token
        assert tokens.refresh_token
        assert tokens.access_expires_in > 0

    async def test_wrong_password_raises(
        self,
        service: AuthService,
        mock_user_repo: AsyncMock,
    ) -> None:
        """Неверный пароль вызывает InvalidCredentialsError."""
        user = _make_user(password_hash=hash_password("right"))
        mock_user_repo.get_by_email.return_value = user

        with pytest.raises(InvalidCredentialsError):
            await service.login("test@example.com", "wrong")

    async def test_nonexistent_email_raises(
        self,
        service: AuthService,
        mock_user_repo: AsyncMock,
    ) -> None:
        """Несуществующий email вызывает InvalidCredentialsError."""
        mock_user_repo.get_by_email.return_value = None

        with pytest.raises(InvalidCredentialsError):
            await service.login("no@example.com", "any")

    async def test_inactive_user_raises(
        self,
        service: AuthService,
        mock_user_repo: AsyncMock,
    ) -> None:
        """Деактивированный пользователь вызывает InvalidCredentialsError."""
        user = _make_user(is_active=False)
        mock_user_repo.get_by_email.return_value = user

        with pytest.raises(InvalidCredentialsError):
            await service.login("test@example.com", "TestPass123!")

    async def test_no_password_hash_raises(
        self,
        service: AuthService,
        mock_user_repo: AsyncMock,
    ) -> None:
        """Пользователь без пароля (Telegram-only) вызывает InvalidCredentialsError."""
        user = _make_user(password_hash=None)
        mock_user_repo.get_by_email.return_value = user

        with pytest.raises(InvalidCredentialsError):
            await service.login("test@example.com", "any")

    async def test_pending_organization_raises(
        self,
        service: AuthService,
        mock_user_repo: AsyncMock,
        mock_org_repo: AsyncMock,
    ) -> None:
        """Организация в статусе pending_moderation вызывает
        OrganizationPendingError."""
        org = _make_org(status=OrganizationStatus.PENDING_MODERATION)
        user = _make_user(org_id=org.id)
        mock_user_repo.get_by_email.return_value = user
        mock_org_repo.get_by_id.return_value = org

        with pytest.raises(OrganizationPendingError):
            await service.login("test@example.com", "TestPass123!")

    async def test_suspended_organization_raises(
        self,
        service: AuthService,
        mock_user_repo: AsyncMock,
        mock_org_repo: AsyncMock,
    ) -> None:
        """Организация в статусе suspended вызывает OrganizationSuspendedError."""
        org = _make_org(status=OrganizationStatus.SUSPENDED)
        user = _make_user(org_id=org.id)
        mock_user_repo.get_by_email.return_value = user
        mock_org_repo.get_by_id.return_value = org

        with pytest.raises(OrganizationSuspendedError):
            await service.login("test@example.com", "TestPass123!")

    async def test_email_normalized_to_lowercase(
        self,
        service: AuthService,
        mock_user_repo: AsyncMock,
        mock_org_repo: AsyncMock,
    ) -> None:
        """Email приводится к нижнему регистру перед поиском."""
        org = _make_org(status=OrganizationStatus.ACTIVE)
        user = _make_user(email="test@example.com", org_id=org.id)
        mock_user_repo.get_by_email.return_value = user
        mock_org_repo.get_by_id.return_value = org

        await service.login("Test@Example.COM", "TestPass123!")

        mock_user_repo.get_by_email.assert_called_with("test@example.com")


class TestAuthServiceRefresh:
    """Тесты refresh (rotating refresh)."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def mock_user_repo(self) -> AsyncMock:
        return AsyncMock(spec=UserRepository)

    @pytest.fixture
    def mock_org_service(self) -> AsyncMock:
        return AsyncMock(spec=OrganizationService)

    @pytest.fixture
    def mock_redis(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def mock_org_repo(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def test_settings(self) -> Settings:
        return _build_test_settings()

    @pytest.fixture
    def service(
        self,
        mock_session: AsyncMock,
        mock_user_repo: AsyncMock,
        mock_org_service: AsyncMock,
        mock_redis: AsyncMock,
        mock_org_repo: AsyncMock,
        test_settings: Settings,
    ) -> AuthService:
        with patch(
            "paytools.domain.auth.service.get_settings",
            return_value=test_settings,
        ):
            return AuthService(
                mock_session,
                user_repo=mock_user_repo,
                org_service=mock_org_service,
                redis=mock_redis,
                org_repo=mock_org_repo,
            )

    async def test_successful_refresh(
        self,
        service: AuthService,
        mock_user_repo: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Успешный refresh возвращает новую пару токенов."""
        user = _make_user()
        mock_user_repo.get_by_id.return_value = user
        mock_redis.exists.return_value = False  # jti не в блок-листе
        mock_redis.set.return_value = True  # NX захват успешен

        refresh_token = create_refresh_token({"sub": str(user.id)})

        tokens = await service.refresh(refresh_token)

        assert isinstance(tokens, TokenPair)
        assert tokens.access_token
        assert tokens.refresh_token

    async def test_revoked_token_raises(
        self,
        service: AuthService,
        mock_redis: AsyncMock,
    ) -> None:
        """Отозванный токен вызывает InvalidRefreshTokenError."""
        user = _make_user()
        mock_redis.exists.return_value = True  # jti в блок-листе

        refresh_token = create_refresh_token({"sub": str(user.id)})

        with pytest.raises(InvalidRefreshTokenError):
            await service.refresh(refresh_token)

    async def test_race_condition_second_fails(
        self,
        service: AuthService,
        mock_user_repo: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """При гонке второй запрос с тем же токеном падает."""
        user = _make_user()
        mock_user_repo.get_by_id.return_value = user
        mock_redis.exists.return_value = False
        mock_redis.set.return_value = False  # NX захват НЕ успешен (уже занят)

        refresh_token = create_refresh_token({"sub": str(user.id)})

        with pytest.raises(InvalidRefreshTokenError):
            await service.refresh(refresh_token)

    async def test_wrong_token_type_raises(
        self,
        service: AuthService,
    ) -> None:
        """Access-токен вместо refresh вызывает InvalidRefreshTokenError."""
        access_token = create_access_token({"sub": str(uuid4())})

        with pytest.raises(InvalidRefreshTokenError):
            await service.refresh(access_token)

    async def test_invalid_token_raises(
        self,
        service: AuthService,
    ) -> None:
        """Невалидный токен вызывает InvalidRefreshTokenError."""
        with pytest.raises(InvalidRefreshTokenError):
            await service.refresh("not-a-valid-token")

    async def test_user_not_found_raises(
        self,
        service: AuthService,
        mock_user_repo: AsyncMock,
        mock_redis: AsyncMock,
    ) -> None:
        """Пользователь не найден — InvalidRefreshTokenError."""
        mock_user_repo.get_by_id.return_value = None
        mock_redis.exists.return_value = False

        refresh_token = create_refresh_token({"sub": str(uuid4())})

        with pytest.raises(InvalidRefreshTokenError):
            await service.refresh(refresh_token)


class TestAuthServiceLogout:
    """Тесты logout."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def mock_user_repo(self) -> AsyncMock:
        return AsyncMock(spec=UserRepository)

    @pytest.fixture
    def mock_org_service(self) -> AsyncMock:
        return AsyncMock(spec=OrganizationService)

    @pytest.fixture
    def mock_redis(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def mock_org_repo(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def test_settings(self) -> Settings:
        return _build_test_settings()

    @pytest.fixture
    def service(
        self,
        mock_session: AsyncMock,
        mock_user_repo: AsyncMock,
        mock_org_service: AsyncMock,
        mock_redis: AsyncMock,
        mock_org_repo: AsyncMock,
        test_settings: Settings,
    ) -> AuthService:
        with patch(
            "paytools.domain.auth.service.get_settings",
            return_value=test_settings,
        ):
            return AuthService(
                mock_session,
                user_repo=mock_user_repo,
                org_service=mock_org_service,
                redis=mock_redis,
                org_repo=mock_org_repo,
            )

    async def test_logout_adds_jti_to_blocklist(
        self,
        service: AuthService,
        mock_redis: AsyncMock,
    ) -> None:
        """Logout добавляет jti в Redis блок-лист."""
        refresh_token = create_refresh_token({"sub": str(uuid4())})

        await service.logout(refresh_token)

        # Проверяем что setex был вызван с ключом revoked_jti:{jti}
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args[0]
        assert call_args[0].startswith("revoked_jti:")

    async def test_logout_invalid_token_silent(
        self,
        service: AuthService,
        mock_redis: AsyncMock,
    ) -> None:
        """Logout с невалидным токеном молча завершается."""
        await service.logout("not-a-valid-token")

        # setex не должен вызываться
        mock_redis.setex.assert_not_called()

    async def test_logout_idempotent(
        self,
        service: AuthService,
        mock_redis: AsyncMock,
    ) -> None:
        """Повторный logout идемпотентен."""
        refresh_token = create_refresh_token({"sub": str(uuid4())})

        await service.logout(refresh_token)
        await service.logout(refresh_token)

        # setex вызывается оба раза (идемпотентно перезаписывает)
        assert mock_redis.setex.call_count == 2


class TestAuthServiceIssueTokens:
    """Тесты issue_tokens."""

    @pytest.fixture
    def test_settings(self) -> Settings:
        return _build_test_settings()

    @pytest.fixture
    def service(self, test_settings: Settings) -> AuthService:
        with patch(
            "paytools.domain.auth.service.get_settings",
            return_value=test_settings,
        ):
            return AuthService(
                AsyncMock(),
                user_repo=AsyncMock(),
                org_service=AsyncMock(),
                redis=AsyncMock(),
            )

    def test_issue_tokens_contains_correct_claims(self, service: AuthService) -> None:
        """Токены содержат правильные claims."""
        org_id = uuid4()
        user = _make_user(org_id=org_id)

        tokens = service.issue_tokens(user)

        access_payload = decode_token(tokens.access_token)
        assert access_payload["sub"] == str(user.id)
        assert access_payload["org"] == str(org_id)
        assert access_payload["role"] == "organizer"
        assert access_payload["type"] == "access"

        refresh_payload = decode_token(tokens.refresh_token)
        assert refresh_payload["type"] == "refresh"

    def test_issue_tokens_superadmin_no_org(self, service: AuthService) -> None:
        """У superadmin org=None."""
        user = _make_user(role=UserRole.SUPERADMIN, org_id=None)

        tokens = service.issue_tokens(user)

        access_payload = decode_token(tokens.access_token)
        assert access_payload["org"] is None
        assert access_payload["role"] == "superadmin"


class TestAuthServiceVerifyAccess:
    """Тесты verify_access."""

    @pytest.fixture
    def test_settings(self) -> Settings:
        return _build_test_settings()

    @pytest.fixture
    def service(self, test_settings: Settings) -> AuthService:
        with patch(
            "paytools.domain.auth.service.get_settings",
            return_value=test_settings,
        ):
            return AuthService(
                AsyncMock(),
                user_repo=AsyncMock(),
                org_service=AsyncMock(),
                redis=AsyncMock(),
            )

    async def test_verify_valid_access_token(self, service: AuthService) -> None:
        """Валидный access-токен возвращает пользователя."""
        user = _make_user()
        service.user_repo.get_by_id.return_value = user

        token = create_access_token({"sub": str(user.id), "role": "organizer"})
        result = await service.verify_access(token)

        assert result == user

    async def test_verify_wrong_token_type_raises(self, service: AuthService) -> None:
        """Refresh-токен вместо access вызывает AuthError."""
        token = create_refresh_token({"sub": str(uuid4())})

        with pytest.raises(AuthError):
            await service.verify_access(token)

    async def test_verify_user_not_found_raises(self, service: AuthService) -> None:
        """Пользователь не найден вызывает AuthError."""
        service.user_repo.get_by_id.return_value = None

        token = create_access_token({"sub": str(uuid4())})
        with pytest.raises(AuthError):
            await service.verify_access(token)

    async def test_verify_inactive_user_raises(self, service: AuthService) -> None:
        """Неактивный пользователь вызывает AuthError."""
        user = _make_user(is_active=False)
        service.user_repo.get_by_id.return_value = user

        token = create_access_token({"sub": str(user.id)})
        with pytest.raises(AuthError):
            await service.verify_access(token)

    async def test_verify_invalid_token_raises(self, service: AuthService) -> None:
        """Невалидный токен вызывает AuthError."""
        with pytest.raises(AuthError):
            await service.verify_access("not-a-valid-token")
