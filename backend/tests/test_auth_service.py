"""Testes unitários para AuthService.refresh (US-07)."""

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from jose import jwt

from app.adapters.config.settings import Settings
from app.adapters.jwt_token_provider import JwtTokenProvider
from app.application.auth_service import AuthService
from app.domain.exceptions import InvalidTokenError, TokenExpiredError, TokenRevokedError

SECRET = "chave-secreta-de-teste"
ALGORITHM = "HS256"
USER_ID = "usuario-123"
SCOPES = ["user:read", "user:write"]


@pytest.fixture
def settings() -> Settings:
    return Settings(  # type: ignore[call-arg]
        secret_key=SECRET,
        algorithm=ALGORITHM,
        access_token_expire_minutes=30,
        refresh_token_expire_days=7,
    )


@pytest.fixture
def token_provider(settings: Settings) -> JwtTokenProvider:
    return JwtTokenProvider(settings)


@pytest.fixture
def service(token_provider: JwtTokenProvider) -> AuthService:
    return AuthService(token_provider=token_provider)


class TestAuthServiceRefresh:
    # CT-01 (transição de estado): Ativo -> refresh -> Ativo com token válido
    def test_refresh_token_valido_retorna_novo_access_token(
        self, service: AuthService, token_provider: JwtTokenProvider
    ) -> None:
        refresh_token = token_provider.generate_refresh_token(USER_ID)

        access_token = service.refresh(refresh_token)

        payload = token_provider.decode_token(access_token)
        assert payload["sub"] == USER_ID
        assert payload["scopes"] == []

    # CT-02: refresh token expirado lança TokenExpiredError
    def test_refresh_token_expirado_lanca_excecao(self, service: AuthService) -> None:
        expired_payload: dict[str, Any] = {
            "sub": USER_ID,
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        refresh_token = jwt.encode(expired_payload, SECRET, algorithm=ALGORITHM)

        with pytest.raises(TokenExpiredError):
            service.refresh(refresh_token)

    # CT-03: refresh token revogado lança TokenRevokedError
    def test_refresh_token_revogado_lanca_excecao(self, service: AuthService) -> None:
        revoked_payload: dict[str, Any] = {
            "sub": USER_ID,
            "scopes": SCOPES,
            "revoked": True,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        }
        refresh_token = jwt.encode(revoked_payload, SECRET, algorithm=ALGORITHM)

        with pytest.raises(TokenRevokedError):
            service.refresh(refresh_token)

    # CT-04: assinatura adulterada lança InvalidTokenError
    def test_refresh_token_assinatura_adulterada_lanca_excecao(
        self, service: AuthService, token_provider: JwtTokenProvider
    ) -> None:
        refresh_token = token_provider.generate_refresh_token(USER_ID)
        parts = refresh_token.split(".")
        adulterado = parts[0] + "." + parts[1] + ".assinatura_invalida"

        with pytest.raises(InvalidTokenError):
            service.refresh(adulterado)

    # CT-05: payload sem sub lança InvalidTokenError
    def test_refresh_token_sem_sub_lanca_excecao(self, service: AuthService) -> None:
        payload_sem_sub: dict[str, Any] = {
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        }
        refresh_token = jwt.encode(payload_sem_sub, SECRET, algorithm=ALGORITHM)

        with pytest.raises(InvalidTokenError):
            service.refresh(refresh_token)
