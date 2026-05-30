"""Registry de clientes de serviço baseado em configuração (US-28 parte 2).

Lê os clientes das Settings. Em dev há um cliente seedado; em produção os
valores vêm de variáveis de ambiente / cofre de segredos. Implementa o port
`ServiceClientRepository`, então pode ser trocado por um adapter DynamoDB
sem tocar no caso de uso.
"""

from app.adapters.config.settings import Settings
from app.domain.service_client import ServiceClient
from app.ports.service_client_repository import ServiceClientRepository


class ConfigServiceClientRepository(ServiceClientRepository):
    def __init__(self, settings: Settings) -> None:
        scopes = [
            s.strip() for s in settings.service_client_scopes.split(",") if s.strip()
        ]
        self._clients: dict[str, ServiceClient] = {
            settings.service_client_id: ServiceClient(
                client_id=settings.service_client_id,
                secret=settings.service_client_secret,
                scopes=scopes,
            )
        }

    def find_by_client_id(self, client_id: str) -> ServiceClient | None:
        return self._clients.get(client_id)
