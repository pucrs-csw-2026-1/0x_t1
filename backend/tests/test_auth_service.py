from datetime import datetime, timedelta, timezone

import pytest

from app.adapters.config.settings import Settings
from app.adapters.in_memory_refresh_token_repository import InMemoryRefreshTokenRepository
from app.adapters.jwt_token_provider import JwtTokenProvider
from app.application.auth_service import AuthService
from app.domain.exceptions import TokenRevokedError, UserNotFoundError


class SimpleFakeRefreshRepo(InMemoryRefreshTokenRepository):
    pass


@pytest.fixture
def settings() -> Settings:
    return Settings(
        secret_key="test-secret",
        algorithm="HS256",
        access_token_expire_minutes=30,
        refresh_token_expire_days=7,
    )  # type: ignore[call-arg]


@pytest.fixture
def token_provider(settings: Settings) -> JwtTokenProvider:
    return JwtTokenProvider(settings)


def test_logout_revoga_refresh_token(fake_repo, valid_user, token_provider):
    # Arrange
    refresh_repo = SimpleFakeRefreshRepo()
    auth_service = AuthService(user_repo=fake_repo, token_provider=token_provider, refresh_repo=refresh_repo)

    fake_repo.save(valid_user)
    refresh = token_provider.generate_refresh_token(valid_user.id)

    assert not refresh_repo.is_revoked(refresh)

    # Act
    auth_service.logout(refresh)

    # Assert
    assert refresh_repo.is_revoked(refresh)


def test_logout_idempotente_when_already_revoked(fake_repo, valid_user, token_provider):
    refresh_repo = SimpleFakeRefreshRepo()
    auth_service = AuthService(user_repo=fake_repo, token_provider=token_provider, refresh_repo=refresh_repo)

    fake_repo.save(valid_user)
    refresh = token_provider.generate_refresh_token(valid_user.id)

    # revoke once
    auth_service.logout(refresh)

    # revoke again - must not raise
    auth_service.logout(refresh)

    assert refresh_repo.is_revoked(refresh)


def test_refresh_after_logout_raises_revoked(fake_repo, valid_user, token_provider):
    refresh_repo = SimpleFakeRefreshRepo()
    auth_service = AuthService(user_repo=fake_repo, token_provider=token_provider, refresh_repo=refresh_repo)

    fake_repo.save(valid_user)
    refresh = token_provider.generate_refresh_token(valid_user.id)

    # revoke
    auth_service.logout(refresh)

    with pytest.raises(TokenRevokedError):
        auth_service.refresh(refresh)


def test_refresh_valido_retorna_novo_access_token(
    fake_repo, valid_user, token_provider
):
    refresh_repo = SimpleFakeRefreshRepo()
    auth_service = AuthService(
        user_repo=fake_repo, token_provider=token_provider, refresh_repo=refresh_repo
    )

    fake_repo.save(valid_user)
    refresh = token_provider.generate_refresh_token(valid_user.id)

    access = auth_service.refresh(refresh)
    payload = token_provider.decode_token(access)

    assert payload["sub"] == valid_user.id
    assert payload["scopes"] == valid_user.access_level


def test_refresh_usuario_inexistente_lanca_erro(fake_repo, token_provider):
    refresh_repo = SimpleFakeRefreshRepo()
    auth_service = AuthService(user_repo=fake_repo, token_provider=token_provider, refresh_repo=refresh_repo)

    refresh = token_provider.generate_refresh_token("usuario-inexistente")

    with pytest.raises(UserNotFoundError):
        auth_service.refresh(refresh)
