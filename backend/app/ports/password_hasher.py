from abc import ABC, abstractmethod


class PasswordHasher(ABC):
    """Port para hashing e verificação de senhas."""

    @abstractmethod
    def hash(self, password: str) -> str:
        """Gera o hash da senha em texto plano e retorna a string resultante."""
        ...

    @abstractmethod
    def verify(self, password: str, hashed: str) -> bool:
        """Verifica se a senha em texto plano corresponde ao hash fornecido."""
        ...
