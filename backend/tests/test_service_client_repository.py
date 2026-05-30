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


def test_multi_cliente_via_json() -> None:
    """SERVICE_CLIENTS (JSON) registra vários clientes, cada um com seus scopes."""
    clients_json = (
        '[{"client_id": "metrics-service", "secret": "m", '
        '"scopes": ["metrics:read"]}, '
        '{"client_id": "reports-service", "secret": "r", '
        '"scopes": ["reports:read", "reports:write"]}]'
    )
    repo = ConfigServiceClientRepository(
        Settings(service_clients=clients_json)  # type: ignore[call-arg]
    )

    metrics = repo.find_by_client_id("metrics-service")
    reports = repo.find_by_client_id("reports-service")

    assert metrics is not None and metrics.secret == "m"
    assert metrics.scopes == ["metrics:read"]
    assert reports is not None and reports.secret == "r"
    assert reports.scopes == ["reports:read", "reports:write"]


def test_multi_cliente_rejeita_id_fora_da_lista() -> None:
    clients_json = '[{"client_id": "metrics-service", "secret": "m", "scopes": []}]'
    repo = ConfigServiceClientRepository(
        Settings(service_clients=clients_json)  # type: ignore[call-arg]
    )

    assert repo.find_by_client_id("reports-service") is None
