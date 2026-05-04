"""Testes unitários para AuthService (US-06 login e US-08 logout)."""

from __future__ import annotations

from typing import Any
from unittest.mock import create_autospec

import pytest
from jose import jwt

from app.adapters.config.settings import Settings
from app.adapters.in_memory_refresh_token_repository import (
    InMemoryRefreshTokenRepository,
)
from app.adapters.jwt_token_provider import JwtTokenProvider
from app.application.auth_service import AuthService
from app.domain.exceptions import (
    InvalidCredentialsError,
    InvalidTokenError,
    TokenExpiredError,
    TokenRevokedError,
)
from app.domain.user import User
from app.ports.password_hasher import PasswordHasher
from app.ports.token_provider import TokenProvider
from app.ports.user_repository import UserRepository

SECRET = "chave-secreta-de-teste"
ALGORITHM = "HS256"
USER_ID = "usuario-123"
SCOPES = ["user:read", "user:write"]


@pytest.fixture
def user_repository_mock() -> UserRepository:
    return create_autospec(UserRepository, instance=True)


@pytest.fixture
def password_hasher_mock() -> PasswordHasher:
    return create_autospec(PasswordHasher, instance=True)


@pytest.fixture
def token_provider_mock() -> TokenProvider:
    return create_autospec(TokenProvider, instance=True)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        secret_key=SECRET,
        algorithm=ALGORITHM,
        access_token_expire_minutes=30,
        refresh_token_expire_days=7,
    )  # type: ignore[call-arg]


@pytest.fixture
def jwt_token_provider(settings: Settings) -> JwtTokenProvider:
    return JwtTokenProvider(settings)


@pytest.fixture
def auth_service(
    user_repository_mock: UserRepository,
    password_hasher_mock: PasswordHasher,
    token_provider_mock: TokenProvider,
) -> AuthService:
    return AuthService(
        user_repository=user_repository_mock,
        password_hasher=password_hasher_mock,
        token_provider=token_provider_mock,
    )


class TestAuthServiceLogin:
    """Testes do método login (US-06)."""

    def test_login_com_credenciais_validas_retorna_tokens(
        self,
        auth_service: AuthService,
        user_repository_mock: UserRepository,
        password_hasher_mock: PasswordHasher,
        token_provider_mock: TokenProvider,
        valid_user: User,
    ) -> None:
        """CT-01: Login com email e senha válidos retorna tokens."""
        user_repository_mock.find_by_email.return_value = valid_user
        password_hasher_mock.verify.return_value = True
        token_provider_mock.generate_access_token.return_value = "access.jwt"
        token_provider_mock.generate_refresh_token.return_value = "refresh.jwt"

        result = auth_service.login(
            email=valid_user.email.value, password="Senha@123"
        )

        assert result == {
            "access_token": "access.jwt",
            "refresh_token": "refresh.jwt",
            "token_type": "bearer",
        }
        password_hasher_mock.verify.assert_called_once()
        token_provider_mock.generate_access_token.assert_called_once()

    def test_login_com_email_inexistente_lanca_erro(
        self,
        auth_service: AuthService,
        user_repository_mock: UserRepository,
        password_hasher_mock: PasswordHasher,
        token_provider_mock: TokenProvider,
    ) -> None:
        """CT-02: Email inexistente lança InvalidCredentialsError."""
        user_repository_mock.find_by_email.return_value = None

        with pytest.raises(InvalidCredentialsError):
            auth_service.login(email="naoexiste@example.com", password="Senha@123")

        password_hasher_mock.verify.assert_not_called()
        token_provider_mock.generate_access_token.assert_not_called()

    def test_login_com_senha_incorreta_lanca_erro(
        self,
        auth_service: AuthService,
        user_repository_mock: UserRepository,
        password_hasher_mock: PasswordHasher,
        token_provider_mock: TokenProvider,
        valid_user: User,
    ) -> None:
        """CT-03: Senha incorreta lança InvalidCredentialsError."""
        user_repository_mock.find_by_email.return_value = valid_user
        password_hasher_mock.verify.return_value = False

        with pytest.raises(InvalidCredentialsError):
            auth_service.login(
                email=valid_user.email.value, password="SenhaErrada@1"
            )

        token_provider_mock.generate_access_token.assert_not_called()


class TestAuthServiceRefresh:
    """Testes do método refresh (US-06 + US-08)."""

    def test_refresh_token_valido_retorna_novo_access_token(
        self,
        user_repository_mock: UserRepository,
        password_hasher_mock: PasswordHasher,
        jwt_token_provider: JwtTokenProvider,
    ) -> None:
        """CT-04: Refresh token válido retorna novo access token."""
        auth_service = AuthService(
            user_repository=user_repository_mock,
            password_hasher=password_hasher_mock,
            token_provider=jwt_token_provider,
        )
        refresh_token = jwt_token_provider.generate_refresh_token(USER_ID)

        access_token = auth_service.refresh(refresh_token)

        payload = jwt_token_provider.decode_token(access_token)
        assert payload["sub"] == USER_ID

    def test_refresh_token_expirado_lanca_excecao(
        self,
        user_repository_mock: UserRepository,
        password_hasher_mock: PasswordHasher,
        jwt_token_provider: JwtTokenProvider,
    ) -> None:
        """CT-05: Refresh token expirado lança TokenExpiredError."""
        from datetime import datetime, timedelta, timezone

        auth_service = AuthService(
            user_repository=user_repository_mock,
            password_hasher=password_hasher_mock,
            token_provider=jwt_token_provider,
        )
        expired_payload: dict[str, Any] = {
            "sub": USER_ID,
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        refresh_token = jwt.encode(expired_payload, SECRET, algorithm=ALGORITHM)

        with pytest.raises(TokenExpiredError):
            auth_service.refresh(refresh_token)

    def test_refresh_token_invalido_lanca_excecao(
        self,
        user_repository_mock: UserRepository,
        password_hasher_mock: PasswordHasher,
        jwt_token_provider: JwtTokenProvider,
    ) -> None:
        """CT-06: Refresh token com assinatura inválida lança InvalidTokenError."""
        auth_service = AuthService(
            user_repository=user_repository_mock,
            password_hasher=password_hasher_mock,
            token_provider=jwt_token_provider,
        )
        refresh_token = jwt_token_provider.generate_refresh_token(USER_ID)
        parts = refresh_token.split(".")
        adulterado = parts[0] + "." + parts[1] + ".assinatura_invalida"

        with pytest.raises(InvalidTokenError):
            auth_service.refresh(adulterado)


class TestAuthServiceLogout:
    """Testes do método logout (US-08)."""

    def test_logout_revoga_refresh_token(
        self,
        user_repository_mock: UserRepository,
        password_hasher_mock: PasswordHasher,
        jwt_token_provider: JwtTokenProvider,
        valid_user: User,
    ) -> None:
        """CT-07: Logout marca refresh token como revogado."""
        refresh_repo = InMemoryRefreshTokenRepository()
        auth_service = AuthService(
            user_repository=user_repository_mock,
            password_hasher=password_hasher_mock,
            token_provider=jwt_token_provider,
            refresh_repository=refresh_repo,
        )
        refresh = jwt_token_provider.generate_refresh_token(valid_user.id)

        assert not refresh_repo.is_revoked(refresh)
        auth_service.logout(refresh)
        assert refresh_repo.is_revoked(refresh)

    def test_logout_idempotente(
        self,
        user_repository_mock: UserRepository,
        password_hasher_mock: PasswordHasher,
        jwt_token_provider: JwtTokenProvider,
        valid_user: User,
    ) -> None:
        """CT-08: Logout de token já revogado é idempotente."""
        refresh_repo = InMemoryRefreshTokenRepository()
        auth_service = AuthService(
            user_repository=user_repository_mock,
            password_hasher=password_hasher_mock,
            token_provider=jwt_token_provider,
            refresh_repository=refresh_repo,
        )
        refresh = jwt_token_provider.generate_refresh_token(valid_user.id)

        auth_service.logout(refresh)
        auth_service.logout(refresh)  # Sem erro
        assert refresh_repo.is_revoked(refresh)

    def test_refresh_apos_logout_lanca_revoked(
        self,
        user_repository_mock: UserRepository,
        password_hasher_mock: PasswordHasher,
        jwt_token_provider: JwtTokenProvider,
        valid_user: User,
    ) -> None:
        """CT-09: Refresh após logout lança TokenRevokedError."""
        refresh_repo = InMemoryRefreshTokenRepository()
        auth_service = AuthService(
            user_repository=user_repository_mock,
            password_hasher=password_hasher_mock,
            token_provider=jwt_token_provider,
            refresh_repository=refresh_repo,
        )
        refresh = jwt_token_provider.generate_refresh_token(valid_user.id)

        auth_service.logout(refresh)
        with pytest.raises(TokenRevokedError):
            auth_service.refresh(refresh)

