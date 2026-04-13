from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.domain.exceptions import (
    InvalidEmailError,
    InvalidNameError,
    InvalidUsernameError,
    WeakPasswordError,
)

# --- Value Objects ---

_EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
_USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_.]{8,25}$")


class Email:
    """Value object - e-mail validado e imutável."""

    def __init__(self, address: str) -> None:
        if not address or not _EMAIL_REGEX.match(address):
            raise InvalidEmailError(address)
        self._address = address.lower().strip()

    @property
    def value(self) -> str:
        return self._address

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Email):
            return NotImplemented
        return self._address == other._address

    def __hash__(self) -> int:
        return hash(self._address)


class Username:
    """Value object - nome de usuário validado e imutável."""

    def __init__(self, value: str) -> None:
        stripped = value.strip()
        if len(stripped) < 8:
            raise InvalidUsernameError("username deve ter ao menos 8 caracteres")
        if len(stripped) > 25:
            raise InvalidUsernameError("username deve ter no máximo 25 caracteres")
        if not _USERNAME_REGEX.match(stripped):
            raise InvalidUsernameError(
                "username deve conter apenas letras, números, _, pontos"
            )
        self._value = stripped.lower()

    @property
    def value(self) -> str:
        return self._value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Username):
            return NotImplemented
        return self._value == other._value

    def __hash__(self) -> int:
        return hash(self._value)


class HashedPassword:
    """Value object - senha hasheada"""

    def __init__(self, value: str) -> None:
        if not value:
            raise ValueError("senha hasheada não pode ser vazia")
        self._value = value

    @property
    def value(self) -> str:
        return self._value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, HashedPassword):
            return NotImplemented
        return self._value == other._value

    def __hash__(self) -> int:
        return hash(self._value)

    def __repr__(self) -> str:
        return "HashedPassword(***)"


# --- Validações de entrada ---


def validate_raw_password(password: str) -> None:
    if len(password) < 8:
        raise WeakPasswordError("deve ter ao menos 8 caracteres")
    if not re.search(r"[A-Z]", password):
        raise WeakPasswordError("deve conter ao menos uma letra maiúscula")
    if not re.search(r"[a-z]", password):
        raise WeakPasswordError("deve conter ao menos uma letra minúscula")
    if not re.search(r"\d", password):
        raise WeakPasswordError("deve conter ao menos um número")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        raise WeakPasswordError("deve conter ao menos um caractere especial")


def validate_name_field(value: str, field_name: str) -> str:
    """Valida first_name ou last_name: 1 a 255 chars"""
    stripped = value.strip()
    if len(stripped) < 1:
        raise InvalidNameError(f"{field_name} não pode ser vazio")
    if len(stripped) > 255:
        raise InvalidNameError(f"{field_name} deve ter no máximo 255 caracteres")
    return stripped


# --- Entidade ---


@dataclass
class User:
    """Entidade raíz do domínio.
    - `id` e `created_at` são imutáveis (identidade da entidade)
    - demais campos podem ser atualizados (mutabilidade da entidade)
    """

    username: Username
    email: Email
    hashed_password: HashedPassword
    first_name: str
    last_name: str
    access_level: list[str] = field(default_factory=list)
    is_active: bool = True
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        # Validações adicionais
        self.first_name = validate_name_field(self.first_name, "first_name")
        self.last_name = validate_name_field(self.last_name, "last_name")

    # --- Métodos de mutação ---

    def change_email(self, new_email: Email) -> None:
        self.email = new_email
        self._touch()

    def change_username(self, new_username: Username) -> None:
        self.username = new_username
        self._touch()

    def change_password(self, new_hashed_password: HashedPassword) -> None:
        self.hashed_password = new_hashed_password
        self._touch()

    def change_name(self, new_first_name: str, new_last_name: str) -> None:
        self.first_name = validate_name_field(new_first_name, "first_name")
        self.last_name = validate_name_field(new_last_name, "last_name")
        self._touch()

    def deactivate(self) -> None:
        self.is_active = False
        self._touch()

    def activate(self) -> None:
        self.is_active = True
        self._touch()

    def _touch(self) -> None:
        """Atualiza o timestamp de atualização."""
        self.updated_at = datetime.now(timezone.utc)
