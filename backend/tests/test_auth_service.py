"""Testes unitarios para AuthService (US-07: renovacao automatica da sessao)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import create_autospec

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from app.adapters.api.auth_router import router
from app.adapters.api.dependencies import get_auth_service
from app.adapters.config.settings import Settings
from app.adapters.jwt_token_provider import JwtTokenProvider
from app.application.auth_service import AuthService
from app.domain.exceptions import (
    InvalidCredentialsError,
    InvalidTokenError,
    TokenExpiredError,
    TokenRevokedError,
)
from app.domain.user import Email, User
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


def test_login_com_credenciais_validas_retorna_tokens(
    auth_service: AuthService,
    user_repository_mock: UserRepository,
    password_hasher_mock: PasswordHasher,
    token_provider_mock: TokenProvider,
    valid_user: User,
) -> None:
    user_repository_mock.find_by_email.return_value = valid_user
    password_hasher_mock.verify.return_value = True
    token_provider_mock.generate_access_token.return_value = "access.jwt"
    token_provider_mock.generate_refresh_token.return_value = "refresh.jwt"

    result = auth_service.login(email=valid_user.email.value, password="Senha@123")

    assert result == {
        "access_token": "access.jwt",
        "refresh_token": "refresh.jwt",
        "token_type": "bearer",
    }
    user_repository_mock.find_by_email.assert_called_once()
    email_arg = user_repository_mock.find_by_email.call_args.args[0]
    assert isinstance(email_arg, Email)
    assert email_arg.value == valid_user.email.value
    password_hasher_mock.verify.assert_called_once_with(
        "Senha@123", valid_user.hashed_password.value
    )
    token_provider_mock.generate_access_token.assert_called_once_with(
        user_id=valid_user.id,
        scopes=valid_user.access_level,
    )
    token_provider_mock.generate_refresh_token.assert_called_once_with(
        user_id=valid_user.id,
    )


def test_login_com_email_inexistente_lanca_invalid_credentials_error(
    auth_service: AuthService,
    user_repository_mock: UserRepository,
    password_hasher_mock: PasswordHasher,
    token_provider_mock: TokenProvider,
) -> None:
    user_repository_mock.find_by_email.return_value = None

    with pytest.raises(InvalidCredentialsError):
        auth_service.login(email="naoexiste@example.com", password="Senha@123")

    password_hasher_mock.verify.assert_not_called()
    token_provider_mock.generate_access_token.assert_not_called()
    token_provider_mock.generate_refresh_token.assert_not_called()


def test_login_com_senha_incorreta_lanca_invalid_credentials_error(
    auth_service: AuthService,
    user_repository_mock: UserRepository,
    password_hasher_mock: PasswordHasher,
    token_provider_mock: TokenProvider,
    valid_user: User,
) -> None:
    user_repository_mock.find_by_email.return_value = valid_user
    password_hasher_mock.verify.return_value = False

    with pytest.raises(InvalidCredentialsError):
        auth_service.login(email=valid_user.email.value, password="SenhaErrada@1")

    token_provider_mock.generate_access_token.assert_not_called()
    token_provider_mock.generate_refresh_token.assert_not_called()


def test_post_auth_login_aceita_form_urlencoded() -> None:
    app = FastAPI()
    auth_service_mock = create_autospec(AuthService, instance=True)
    auth_service_mock.login.return_value = {
        "access_token": "access.jwt",
        "refresh_token": "refresh.jwt",
        "token_type": "bearer",
    }

    app.include_router(router)
    app.dependency_overrides[get_auth_service] = lambda: auth_service_mock

    client = TestClient(app)
    response = client.post(
        "/auth/login",
        data={"username": "maria@example.com", "password": "Senha@123"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "access_token": "access.jwt",
        "refresh_token": "refresh.jwt",
        "token_type": "bearer",
    }
    auth_service_mock.login.assert_called_once_with(
        email="maria@example.com",
        password="Senha@123",
    )


def test_post_auth_login_retorna_401_quando_credenciais_sao_invalidas() -> None:
    app = FastAPI()
    auth_service_mock = create_autospec(AuthService, instance=True)
    auth_service_mock.login.side_effect = InvalidCredentialsError()

    app.include_router(router)
    app.dependency_overrides[get_auth_service] = lambda: auth_service_mock

    client = TestClient(app)
    response = client.post(
        "/auth/login",
        data={"username": "maria@example.com", "password": "SenhaErrada@1"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Credenciais inválidas."}
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.fixture
def settings() -> Settings:
    return Settings(  # type: ignore[call-arg]
        secret_key=SECRET,
        algorithm=ALGORITHM,
        access_token_expire_minutes=30,
        refresh_token_expire_days=7,
    )


@pytest.fixture
def jwt_token_provider(settings: Settings) -> JwtTokenProvider:
    return JwtTokenProvider(settings)


@pytest.fixture
def refresh_service(
    jwt_token_provider: JwtTokenProvider,
    user_repository_mock: UserRepository,
    password_hasher_mock: PasswordHasher,
) -> AuthService:
    return AuthService(
        user_repository=user_repository_mock,
        password_hasher=password_hasher_mock,
        token_provider=jwt_token_provider,
    )


def test_refresh_token_valido_retorna_novo_access_token(
    refresh_service: AuthService,
    jwt_token_provider: JwtTokenProvider,
) -> None:
    refresh_token = jwt_token_provider.generate_refresh_token(USER_ID)

    access_token = refresh_service.refresh(refresh_token)

    payload = jwt_token_provider.decode_token(access_token)
    assert payload["sub"] == USER_ID
    assert payload["scopes"] == []


def test_refresh_token_expirado_lanca_excecao(refresh_service: AuthService) -> None:
    expired_payload: dict[str, Any] = {
        "sub": USER_ID,
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
    }
    refresh_token = jwt.encode(expired_payload, SECRET, algorithm=ALGORITHM)

    with pytest.raises(TokenExpiredError):
        refresh_service.refresh(refresh_token)


def test_refresh_token_revogado_lanca_excecao(refresh_service: AuthService) -> None:
    revoked_payload: dict[str, Any] = {
        "sub": USER_ID,
        "scopes": SCOPES,
        "revoked": True,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
    }
    refresh_token = jwt.encode(revoked_payload, SECRET, algorithm=ALGORITHM)

    with pytest.raises(TokenRevokedError):
        refresh_service.refresh(refresh_token)


def test_refresh_token_assinatura_adulterada_lanca_excecao(
    refresh_service: AuthService,
    jwt_token_provider: JwtTokenProvider,
) -> None:
    refresh_token = jwt_token_provider.generate_refresh_token(USER_ID)
    parts = refresh_token.split(".")
    adulterado = parts[0] + "." + parts[1] + ".assinatura_invalida"

    with pytest.raises(InvalidTokenError):
        refresh_service.refresh(adulterado)


def test_refresh_token_sem_sub_lanca_excecao(refresh_service: AuthService) -> None:
    payload_sem_sub: dict[str, Any] = {
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
    }
    refresh_token = jwt.encode(payload_sem_sub, SECRET, algorithm=ALGORITHM)

    with pytest.raises(InvalidTokenError):
        refresh_service.refresh(refresh_token)
