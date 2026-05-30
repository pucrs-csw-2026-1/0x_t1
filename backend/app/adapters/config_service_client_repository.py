"""Registry de clientes de serviço baseado em configuração (US-28 parte 2).

Suporta múltiplos clientes via `SERVICE_CLIENTS` (JSON); na ausência, cai no
cliente único seedado de dev (SERVICE_CLIENT_*). Implementa o port
`ServiceClientRepository`, então pode ser trocado por um adapter DynamoDB
sem tocar no caso de uso.
"""

import json
from typing import Any

from app.adapters.config.settings import Settings
from app.domain.service_client import ServiceClient
from app.ports.service_client_repository import ServiceClientRepository


def _parse_scopes(raw: Any) -> list[str]:
    """Aceita scopes como lista JSON ou string separada por vírgula."""
    if isinstance(raw, str):
        return [s.strip() for s in raw.split(",") if s.strip()]
    return [str(s).strip() for s in (raw or []) if str(s).strip()]


class ConfigServiceClientRepository(ServiceClientRepository):
    def __init__(self, settings: Settings) -> None:
        self._clients: dict[str, ServiceClient] = {}

        if settings.service_clients:
            # Multi-cliente via JSON.
            entries = json.loads(settings.service_clients)
            for entry in entries:
                client = ServiceClient(
                    client_id=entry["client_id"],
                    secret=entry["secret"],
                    scopes=_parse_scopes(entry.get("scopes")),
                )
                self._clients[client.client_id] = client
        else:
            # Fallback: cliente único seedado de dev.
            self._clients[settings.service_client_id] = ServiceClient(
                client_id=settings.service_client_id,
                secret=settings.service_client_secret,
                scopes=_parse_scopes(settings.service_client_scopes),
            )

    def find_by_client_id(self, client_id: str) -> ServiceClient | None:
        return self._clients.get(client_id)
