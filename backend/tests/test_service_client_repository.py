"""Testes do registry de clientes de serviço via config (US-28 parte 2)."""

from app.adapters.config.settings import Settings
from app.adapters.config_service_client_repository import (
    ConfigServiceClientRepository,
)


def _settings() -> Settings:
    return Settings(  # type: ignore[call-arg]
        service_client_id="svc-x",
        service_client_secret="sek",
        service_client_scopes="metrics:read, reports:read",
    )


def test_find_cliente_existente_retorna_service_client() -> None:
    repo = ConfigServiceClientRepository(_settings())

    client = repo.find_by_client_id("svc-x")

    assert client is not None
    assert client.client_id == "svc-x"
    assert client.secret == "sek"
    assert client.scopes == ["metrics:read", "reports:read"]


def test_find_cliente_desconhecido_retorna_none() -> None:
    repo = ConfigServiceClientRepository(_settings())

    assert repo.find_by_client_id("nao-existe") is None
