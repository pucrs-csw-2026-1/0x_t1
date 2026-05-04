from __future__ import annotations

from unittest.mock import create_autospec

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.adapters.api.auth_router import get_auth_service, router
from app.application.auth_service import AuthService
from app.domain.exceptions import InvalidCredentialsError
from app.domain.user import Email, User
from app.ports.password_hasher import PasswordHasher
from app.ports.token_provider import TokenProvider
from app.ports.user_repository import UserRepository


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


def test_get_auth_service_levanta_not_implemented_error() -> None:
    with pytest.raises(NotImplementedError):
        get_auth_service()
