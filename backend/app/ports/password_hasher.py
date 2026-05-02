from abc import ABC, abstractmethod


class PasswordHasher(ABC):
    """Port para hashing e verificacao de senha."""

    @abstractmethod
    def verify(self, password: str, hashed: str) -> bool:
        """Valida se a senha em texto plano corresponde ao hash armazenado."""
        ...
