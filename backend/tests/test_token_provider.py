"""Testes unitários para JwtTokenProvider (US-05, RS256 na US-28)."""

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest
from jose import jwt

from app.adapters.config.settings import Settings, read_key
from app.adapters.jwt_token_provider import JwtTokenProvider
from app.domain.exceptions import InvalidTokenError, TokenExpiredError
from app.ports.token_provider import TokenProvider

ALGORITHM = "RS256"
USER_ID = "usuario-123"
SCOPES = ["participant", "manager"]

# Chaves de dev versionadas (mesmas que a app usa); paths relativos a backend/.
PRIVATE_KEY = read_key("keys/dev_private.pem")
PUBLIC_KEY = read_key("keys/dev_public.pem")


@pytest.fixture
def settings() -> Settings:
    return Settings(algorithm=ALGORITHM)  # type: ignore[call-arg]


@pytest.fixture
def provider(settings: Settings) -> JwtTokenProvider:
    return JwtTokenProvider(settings)


class TestJwtTokenProvider:
    # CT-01: access token contém claims sub, scopes, principal_type, exp
    def test_access_token_contem_claims_obrigatorios(
        self, provider: JwtTokenProvider
    ) -> None:
        token = provider.generate_access_token(USER_ID, SCOPES)
        payload = jwt.decode(token, PUBLIC_KEY, algorithms=[ALGORITHM])

        assert payload["sub"] == USER_ID
        assert payload["scopes"] == SCOPES
        assert payload["principal_type"] == "user"
        assert "exp" in payload

    # CT-01b: header carrega kid e alg RS256 (para o JWKS casar a chave)
    def test_access_token_header_tem_kid_e_rs256(
        self, provider: JwtTokenProvider, settings: Settings
    ) -> None:
        token = provider.generate_access_token(USER_ID, SCOPES)
        header = jwt.get_unverified_header(token)

        assert header["alg"] == "RS256"
        assert header["kid"] == settings.jwt_kid

    # CT-01c (US-28 p2): service token carrega principal_type=service e sub=client_id
    def test_service_token_principal_type_service(
        self, provider: JwtTokenProvider
    ) -> None:
        token = provider.generate_service_token("metrics-service", ["metrics:read"])
        payload = jwt.decode(token, PUBLIC_KEY, algorithms=[ALGORITHM])

        assert payload["sub"] == "metrics-service"
        assert payload["principal_type"] == "service"
        assert payload["scopes"] == ["metrics:read"]

    # CT-02: refresh token contém claims sub, scopes e exp
    def test_refresh_token_contem_claims_obrigatorios(
        self, provider: JwtTokenProvider
    ) -> None:
        token = provider.generate_refresh_token(USER_ID, SCOPES)
        payload = jwt.decode(token, PUBLIC_KEY, algorithms=[ALGORITHM])

        assert payload["sub"] == USER_ID
        assert payload["scopes"] == SCOPES
        assert "exp" in payload

    def test_refresh_token_sem_scopes_default_lista_vazia(
        self, provider: JwtTokenProvider
    ) -> None:
        """Compatibilidade: chamadas sem o argumento scopes geram lista vazia."""
        token = provider.generate_refresh_token(USER_ID)
        payload = jwt.decode(token, PUBLIC_KEY, algorithms=[ALGORITHM])

        assert payload["scopes"] == []

    # CT-03 (partição — válido): decode_token retorna payload correto
    def test_decode_token_valido_retorna_payload(
        self, provider: JwtTokenProvider
    ) -> None:
        token = provider.generate_access_token(USER_ID, SCOPES)
        payload = provider.decode_token(token)

        assert payload["sub"] == USER_ID
        assert payload["scopes"] == SCOPES

    # CT-04 (partição — expirado): decode_token lança TokenExpiredError
    def test_decode_token_expirado_lanca_excecao(
        self, provider: JwtTokenProvider
    ) -> None:
        expired_payload: dict[str, Any] = {
            "sub": USER_ID,
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        token = jwt.encode(expired_payload, PRIVATE_KEY, algorithm=ALGORITHM)

        with pytest.raises(TokenExpiredError):
            provider.decode_token(token)

    # CT-05 (exceção): decode_token com assinatura adulterada lança InvalidTokenError
    def test_decode_token_assinatura_adulterada_lanca_excecao(
        self, provider: JwtTokenProvider
    ) -> None:
        token = provider.generate_access_token(USER_ID, SCOPES)
        parts = token.split(".")
        adulterado = parts[0] + "." + parts[1] + ".assinatura_invalida"

        with pytest.raises(InvalidTokenError):
            provider.decode_token(adulterado)

    # CT-06 (exceção): decode_token com payload sem sub lança InvalidTokenError
    def test_decode_token_sem_sub_lanca_excecao(
        self, provider: JwtTokenProvider
    ) -> None:
        payload_sem_sub: dict[str, Any] = {
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        }
        token = jwt.encode(payload_sem_sub, PRIVATE_KEY, algorithm=ALGORITHM)

        with pytest.raises(InvalidTokenError):
            provider.decode_token(token)

    # CT-07 (exceção): token assinado com HS256 (segredo) é rejeitado — só RS256
    # é aceito, então uma assinatura simétrica nunca valida contra a chave pública.
    def test_decode_token_algoritmo_diferente_lanca_excecao(
        self, provider: JwtTokenProvider
    ) -> None:
        token = jwt.encode({"sub": USER_ID}, "outra-chave-secreta", algorithm="HS256")

        with pytest.raises(InvalidTokenError):
            provider.decode_token(token)

    # CT-08a (valor limite): token com exp = agora - 1s é rejeitado
    def test_decode_token_exp_passado_em_1s_lanca_excecao(
        self, provider: JwtTokenProvider
    ) -> None:
        payload: dict[str, Any] = {
            "sub": USER_ID,
            "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
        }
        token = jwt.encode(payload, PRIVATE_KEY, algorithm=ALGORITHM)

        with pytest.raises(TokenExpiredError):
            provider.decode_token(token)

    # CT-08b (valor limite): token com exp = agora + 1s é aceito
    def test_decode_token_exp_futuro_em_1s_retorna_payload(
        self, provider: JwtTokenProvider
    ) -> None:
        payload: dict[str, Any] = {
            "sub": USER_ID,
            "exp": datetime.now(timezone.utc) + timedelta(seconds=1),
        }
        token = jwt.encode(payload, PRIVATE_KEY, algorithm=ALGORITHM)

        result = provider.decode_token(token)
        assert result["sub"] == USER_ID

    # CT-09: JwtTokenProvider implementa o port TokenProvider corretamente
    def test_implementa_abc_sem_erro(self, provider: JwtTokenProvider) -> None:
        assert isinstance(provider, TokenProvider)

    # CT-10 (mock): generate_access_token é chamado com user_id e scopes corretos
    def test_generate_access_token_chamado_com_argumentos_corretos(self) -> None:
        mock: TokenProvider = MagicMock(spec=TokenProvider)
        mock.generate_access_token.return_value = "token.falso.assinado"  # type: ignore[attr-defined]

        result = mock.generate_access_token(USER_ID, SCOPES)  # type: ignore[attr-defined]

        mock.generate_access_token.assert_called_once_with(USER_ID, SCOPES)  # type: ignore[attr-defined]
        assert result == "token.falso.assinado"
