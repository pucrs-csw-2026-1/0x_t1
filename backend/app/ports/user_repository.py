from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.domain.user import Email, User, Username


@dataclass(frozen=True)
class UserPage:
    """Representa uma página de usuários para paginação."""

    items: list[User]
    next_cursor: str | None


class UserRepository(ABC):
    """Port para persistência de usuários."""

    @abstractmethod
    def save(self, user: User) -> User:
        """Persiste o usuário e retorna a entidade salva."""
        ...

    @abstractmethod
    def find_by_email(self, email: Email) -> User | None:
        """Busca um usuário pelo email. Retorna None se não encontrado."""
        ...

    @abstractmethod
    def find_by_username(self, username: Username) -> User | None:
        """Busca um usuário pelo nome de usuário. Retorna None se não encontrado."""
        ...

    @abstractmethod
    def find_by_id(self, id: str) -> User | None:
        """Busca um usuário pelo ID. Retorna None se não encontrado."""
        ...

    @abstractmethod
    def find_all(self, limit: int, cursor: str | None) -> UserPage:
        """Lista até `limit` usuários a partir de `cursor`.

        `cursor` é o `id` do último item da página anterior, ou None para
        começar do início. `next_cursor` no retorno é None quando não há
        mais páginas.

        Importante: `limit` é dica, não garantia. Implementações podem
        retornar menos itens mesmo havendo mais. Confiar em `next_cursor`,
        nunca em `len(items) < limit`, para detectar fim da lista.
        """
        ...
