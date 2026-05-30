from abc import ABC, abstractmethod

from app.domain.service_client import ServiceClient


class ServiceClientRepository(ABC):
    """Port para o catálogo de clientes de serviço (client_credentials)."""

    @abstractmethod
    def find_by_client_id(self, client_id: str) -> ServiceClient | None: ...
