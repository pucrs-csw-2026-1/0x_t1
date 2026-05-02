"""Testes unitários para BcryptPasswordHasher (US-04)."""

from unittest.mock import MagicMock

import pytest

from app.adapters.bcrypt_password_hasher import BcryptPasswordHasher
from app.ports.password_hasher import PasswordHasher

PASSWORD = "S3nh@Forte!"
WRONG_PASSWORD = "outra_senha_errada"


class TestBcryptPasswordHasher:
    @pytest.fixture
    def hasher(self) -> BcryptPasswordHasher:
        return BcryptPasswordHasher()

    # CT-01: hash retorna string diferente da senha original
    def test_hash_difere_da_senha_original(self, hasher: BcryptPasswordHasher) -> None:
        assert hasher.hash(PASSWORD) != PASSWORD

    # CT-02 (partição — classe válida): verify retorna True para senha correta
    def test_verify_retorna_true_para_senha_correta(self, hasher: BcryptPasswordHasher) -> None:
        hashed = hasher.hash(PASSWORD)
        assert hasher.verify(PASSWORD, hashed) is True

    # CT-02 (partição — classe inválida): verify retorna False para senha incorreta
    def test_verify_retorna_false_para_senha_incorreta(self, hasher: BcryptPasswordHasher) -> None:
        hashed = hasher.hash(PASSWORD)
        assert hasher.verify(WRONG_PASSWORD, hashed) is False

    # CT-03: salt aleatório — dois hashes da mesma senha são diferentes
    def test_hash_gera_valores_distintos_por_salt(self, hasher: BcryptPasswordHasher) -> None:
        assert hasher.hash(PASSWORD) != hasher.hash(PASSWORD)

    # CT-04: BcryptPasswordHasher instancia sem TypeError (implementa ABC corretamente)
    def test_implementa_abc_sem_erro(self) -> None:
        instance = BcryptPasswordHasher()
        assert isinstance(instance, PasswordHasher)

    # CT-05 (spy): hash é chamado exatamente 1 vez ao simular cadastro
    def test_hash_chamado_exatamente_uma_vez_no_cadastro(self) -> None:
        spy: PasswordHasher = MagicMock(spec=PasswordHasher)
        spy.hash.return_value = "$2b$12$fakehash"  # type: ignore[attr-defined]

        # Simula a etapa de hashing durante um cadastro
        hashed = spy.hash(PASSWORD)  # type: ignore[attr-defined]

        spy.hash.assert_called_once_with(PASSWORD)  # type: ignore[attr-defined]
        assert hashed == "$2b$12$fakehash"
