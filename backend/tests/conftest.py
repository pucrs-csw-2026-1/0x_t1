"""Fixtures globais compartilhadas entre os testes."""

from typing import Any

import pytest

from app.domain.user import Email, HashedPassword, User, Username


@pytest.fixture
def valid_user_kwargs() -> dict[str, Any]:
    """Kwargs validos para instanciar um User.

    Util para testes que querem alterar apenas um campo mantendo os demais
    validos. Uso:

        def test_x(valid_user_kwargs):
            valid_user_kwargs["first_name"] = ""
            with pytest.raises(InvalidNameError):
                User(**valid_user_kwargs)
    """
    return {
        "username": Username("maria.silva"),
        "email": Email("maria@example.com"),
        "hashed_password": HashedPassword("$2b$12$abcdefghijklmnopqrstuv"),
        "first_name": "Maria",
        "last_name": "Silva",
    }


@pytest.fixture
def valid_user(valid_user_kwargs: dict[str, Any]) -> User:
    """Instancia de User valida para testes que nao precisam customizar."""
    return User(**valid_user_kwargs)
