"""Testes do endpoint JWKS e validação cross-service (US-28)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from app.adapters.api.well_known_router import router
from app.adapters.config.settings import settings
from app.adapters.jwt_token_provider import JwtTokenProvider


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_jwks_expoe_chave_publica_rs256(client: TestClient) -> None:
    """CT-28.JWKS-01: /.well-known/jwks.json devolve a chave pública RS256."""
    resp = client.get("/.well-known/jwks.json")

    assert resp.status_code == 200
    body = resp.json()
    assert "keys" in body and len(body["keys"]) == 1

    key = body["keys"][0]
    assert key["kty"] == "RSA"
    assert key["alg"] == "RS256"
    assert key["use"] == "sig"
    assert key["kid"] == settings.jwt_kid
    # componentes públicas da RSA presentes (sem expor a privada)
    assert key["n"] and key["e"]
    assert "d" not in key  # nunca expor expoente privado


def test_jwks_nao_expoe_chave_privada(client: TestClient) -> None:
    """CT-28.JWKS-02: o JWKS jamais inclui material de chave privada."""
    key = client.get("/.well-known/jwks.json").json()["keys"][0]
    for private_field in ("d", "p", "q", "dp", "dq", "qi"):
        assert private_field not in key


def test_consumidor_valida_token_real_usando_so_o_jwks(client: TestClient) -> None:
    """CT-28.JWKS-03 (cross-service): um consumidor (ex.: Metrics) valida um
    token real emitido pelo Auth usando APENAS a chave pública do JWKS —
    sem segredo compartilhado."""
    # Auth emite o token (assina com a chave privada).
    provider = JwtTokenProvider(settings)
    token = provider.generate_access_token("user-xyz", ["participant", "admin"])

    # Consumidor: pega a chave do JWKS e valida a assinatura por conta própria.
    jwks_key = client.get("/.well-known/jwks.json").json()["keys"][0]
    claims = jwt.decode(token, jwks_key, algorithms=["RS256"])

    assert claims["sub"] == "user-xyz"
    assert claims["principal_type"] == "user"
    assert "admin" in claims["scopes"]
