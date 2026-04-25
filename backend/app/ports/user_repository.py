from abc import ABC, abstractmethod

from app.domain.user import Email, User, Username


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
