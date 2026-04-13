"""Testes unitarios da camada de dominio (US-01).

Aplica as tecnicas descritas em TESTING.md:
- Particao de equivalencia (classes de entrada validas vs. invalidas)
- Analise de valor limite (bordas dos intervalos aceitos)
- Cobertura de decisao (todos os branches de validacao)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import pytest

from app.domain.exceptions import (
    InvalidEmailError,
    InvalidNameError,
    InvalidUsernameError,
    WeakPasswordError,
)
from app.domain.user import (
    Email,
    HashedPassword,
    User,
    Username,
    validate_name_field,
    validate_raw_password,
)

# ═══════════════════════════════════════════════════════════════════
# Email — value object
# ═══════════════════════════════════════════════════════════════════


class TestEmail:
    """Particao de equivalencia: e-mails validos vs. invalidos."""

    @pytest.mark.parametrize(
        "address",
        [
            "user@example.com",
            "first.last@example.com",
            "user@sub.domain.com",
            "a+tag@example.com",
            "x@y.co",
        ],
    )
    def test_aceita_emails_validos(self, address: str) -> None:
        email = Email(address)
        assert email.value == address.lower()

    @pytest.mark.parametrize(
        "address,caso",
        [
            ("", "vazio"),
            ("semArroba", "sem @"),
            ("@semUsuario.com", "sem usuario antes do @"),
            ("sem@dominio", "sem TLD"),
            ("semDominio@", "sem dominio"),
        ],
    )
    def test_rejeita_emails_invalidos(self, address: str, caso: str) -> None:
        with pytest.raises(InvalidEmailError):
            Email(address)

    def test_normaliza_para_lowercase(self) -> None:
        email = Email("User@Example.COM")
        assert email.value == "user@example.com"

    def test_emails_iguais_sao_iguais(self) -> None:
        assert Email("A@B.COM") == Email("a@b.com")

    def test_emails_diferentes_nao_sao_iguais(self) -> None:
        assert Email("a@b.com") != Email("x@y.com")

    def test_email_e_hashavel(self) -> None:
        # Deve poder ser usado em set / dict keys
        conjunto = {Email("a@b.com"), Email("A@B.COM")}
        assert len(conjunto) == 1


# ═══════════════════════════════════════════════════════════════════
# Username — value object
# ═══════════════════════════════════════════════════════════════════


class TestUsername:
    """Valores-limite: 7 (rejeita), 8 (aceita), 25 (aceita), 26 (rejeita)."""

    def test_username_7_chars_rejeita(self) -> None:
        with pytest.raises(InvalidUsernameError, match="8 caracteres"):
            Username("abc1234")  # 7 chars

    def test_username_8_chars_aceita(self) -> None:
        username = Username("abcd1234")  # 8 chars
        assert username.value == "abcd1234"

    def test_username_25_chars_aceita(self) -> None:
        valor = "a" * 25
        username = Username(valor)
        assert username.value == valor

    def test_username_26_chars_rejeita(self) -> None:
        with pytest.raises(InvalidUsernameError, match="25 caracteres"):
            Username("a" * 26)

    @pytest.mark.parametrize(
        "valor",
        [
            "maria.silva",
            "user_name",
            "abc12345",
            "dots.and_underscores",
        ],
    )
    def test_aceita_caracteres_validos(self, valor: str) -> None:
        assert Username(valor).value == valor.lower()

    @pytest.mark.parametrize(
        "valor,caso",
        [
            ("maria silva", "espaco"),
            ("user-name", "hifen"),
            ("user@name", "arroba"),
            ("user!name", "exclamacao"),
        ],
    )
    def test_rejeita_caracteres_invalidos(self, valor: str, caso: str) -> None:
        with pytest.raises(InvalidUsernameError):
            Username(valor)

    def test_normaliza_para_lowercase(self) -> None:
        assert Username("Maria.Silva").value == "maria.silva"

    def test_usernames_iguais_sao_iguais(self) -> None:
        assert Username("abcd1234") == Username("ABCD1234")


# ═══════════════════════════════════════════════════════════════════
# HashedPassword — value object
# ═══════════════════════════════════════════════════════════════════


class TestHashedPassword:
    def test_aceita_valor_nao_vazio(self) -> None:
        hp = HashedPassword("$2b$12$abc")
        assert hp.value == "$2b$12$abc"

    def test_rejeita_valor_vazio(self) -> None:
        with pytest.raises(ValueError):
            HashedPassword("")

    def test_repr_nao_expoe_hash(self) -> None:
        hp = HashedPassword("$2b$12$segredo_super_secreto")
        assert "segredo" not in repr(hp)
        assert repr(hp) == "HashedPassword(***)"

    def test_hashed_passwords_iguais_sao_iguais(self) -> None:
        assert HashedPassword("$2b$12$abc") == HashedPassword("$2b$12$abc")


# ═══════════════════════════════════════════════════════════════════
# validate_raw_password — valida senha antes do hashing
# ═══════════════════════════════════════════════════════════════════


class TestValidateRawPassword:
    """Valores-limite: 7 (rejeita), 8 (aceita), 9 (aceita).
    Cobertura de decisao: cada branch de validacao (tamanho, upper, lower,
    digito, especial) e exercitado.
    """

    # ─── Valor-limite: tamanho ──────────────────────────

    def test_senha_7_chars_rejeita(self) -> None:
        with pytest.raises(WeakPasswordError, match="8 caracteres"):
            validate_raw_password("Aa1!bcd")  # 7 chars

    def test_senha_8_chars_aceita(self) -> None:
        validate_raw_password("Aa1!bcde")  # 8 chars — nao deve levantar

    def test_senha_9_chars_aceita(self) -> None:
        validate_raw_password("Aa1!bcdef")  # 9 chars — nao deve levantar

    # ─── Cobertura de decisao: cada criterio ──────────

    def test_sem_maiuscula_rejeita(self) -> None:
        with pytest.raises(WeakPasswordError, match="maiúscula"):
            validate_raw_password("aa1!bcde")

    def test_sem_minuscula_rejeita(self) -> None:
        with pytest.raises(WeakPasswordError, match="minúscula"):
            validate_raw_password("AA1!BCDE")

    def test_sem_numero_rejeita(self) -> None:
        with pytest.raises(WeakPasswordError, match="número"):
            validate_raw_password("Aa!!bcde")

    def test_sem_especial_rejeita(self) -> None:
        with pytest.raises(WeakPasswordError, match="especial"):
            validate_raw_password("Aa1bcdef")

    def test_senha_com_todos_criterios_aceita(self) -> None:
        # Particao de equivalencia: classe valida completa
        validate_raw_password("MinhaSenha123!")


# ═══════════════════════════════════════════════════════════════════
# validate_name_field — first_name / last_name
# ═══════════════════════════════════════════════════════════════════


class TestValidateNameField:
    """Valores-limite: 0 (rejeita), 1 (aceita), 255 (aceita), 256 (rejeita)."""

    def test_nome_vazio_rejeita(self) -> None:
        with pytest.raises(InvalidNameError, match="não pode ser vazio"):
            validate_name_field("", "first_name")

    def test_nome_so_espacos_rejeita(self) -> None:
        with pytest.raises(InvalidNameError):
            validate_name_field("   ", "first_name")

    def test_nome_1_char_aceita(self) -> None:
        assert validate_name_field("A", "first_name") == "A"

    def test_nome_255_chars_aceita(self) -> None:
        valor = "A" * 255
        assert validate_name_field(valor, "first_name") == valor

    def test_nome_256_chars_rejeita(self) -> None:
        with pytest.raises(InvalidNameError, match="255 caracteres"):
            validate_name_field("A" * 256, "first_name")

    def test_nome_e_stripped(self) -> None:
        assert validate_name_field("  Maria  ", "first_name") == "Maria"

    def test_mensagem_de_erro_cita_o_campo(self) -> None:
        with pytest.raises(InvalidNameError, match="last_name"):
            validate_name_field("", "last_name")


# ═══════════════════════════════════════════════════════════════════
# User — entidade
# ═══════════════════════════════════════════════════════════════════


class TestUserCreation:
    """Criacao e valores padrao da entidade User."""

    def test_gera_id_uuid_automaticamente(self, valid_user: User) -> None:
        # Deve ser um UUID valido
        uuid.UUID(valid_user.id)  # levanta ValueError se nao for

    def test_ids_sao_unicos_por_instancia(
        self, valid_user_kwargs: dict[str, Any]
    ) -> None:
        u1 = User(**valid_user_kwargs)
        u2 = User(**valid_user_kwargs)
        assert u1.id != u2.id

    def test_gera_created_at_automaticamente(self, valid_user: User) -> None:
        assert isinstance(valid_user.created_at, datetime)
        assert valid_user.created_at.tzinfo is not None  # deve ser timezone-aware

    def test_created_at_e_utc(self, valid_user: User) -> None:
        assert valid_user.created_at.utcoffset() == timezone.utc.utcoffset(None)

    def test_gera_updated_at_automaticamente(self, valid_user: User) -> None:
        assert isinstance(valid_user.updated_at, datetime)

    def test_access_level_padrao_e_lista_vazia(self, valid_user: User) -> None:
        assert valid_user.access_level == []

    def test_is_active_padrao_e_true(self, valid_user: User) -> None:
        assert valid_user.is_active is True

    def test_first_name_vazio_rejeita(self, valid_user_kwargs: dict[str, Any]) -> None:
        valid_user_kwargs["first_name"] = ""
        with pytest.raises(InvalidNameError):
            User(**valid_user_kwargs)

    def test_last_name_vazio_rejeita(self, valid_user_kwargs: dict[str, Any]) -> None:
        valid_user_kwargs["last_name"] = ""
        with pytest.raises(InvalidNameError):
            User(**valid_user_kwargs)


# ═══════════════════════════════════════════════════════════════════
# User — metodos de mutacao
# ═══════════════════════════════════════════════════════════════════


class TestUserMutation:
    """Mutacoes preservam `id` e `created_at`, mas atualizam `updated_at`."""

    def test_change_email_preserva_id(self, valid_user: User) -> None:
        id_original = valid_user.id
        valid_user.change_email(Email("nova@example.com"))
        assert valid_user.id == id_original
        assert valid_user.email.value == "nova@example.com"

    def test_change_email_atualiza_updated_at(self, valid_user: User) -> None:
        updated_antes = valid_user.updated_at
        # forca diferenca temporal garantida
        valid_user.updated_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
        valid_user.change_email(Email("nova@example.com"))
        assert valid_user.updated_at > datetime(2000, 1, 1, tzinfo=timezone.utc)
        _ = updated_antes  # silencia linter de var nao usada

    def test_change_username_preserva_id(self, valid_user: User) -> None:
        id_original = valid_user.id
        valid_user.change_username(Username("novo.username"))
        assert valid_user.id == id_original
        assert valid_user.username.value == "novo.username"

    def test_change_password_preserva_id(self, valid_user: User) -> None:
        id_original = valid_user.id
        valid_user.change_password(HashedPassword("$2b$12$novo"))
        assert valid_user.id == id_original
        assert valid_user.hashed_password.value == "$2b$12$novo"

    def test_change_name_preserva_id(self, valid_user: User) -> None:
        id_original = valid_user.id
        valid_user.change_name("Ana", "Souza")
        assert valid_user.id == id_original
        assert valid_user.first_name == "Ana"
        assert valid_user.last_name == "Souza"

    def test_change_name_valida_first_name(self, valid_user: User) -> None:
        with pytest.raises(InvalidNameError):
            valid_user.change_name("", "Souza")

    def test_change_name_valida_last_name(self, valid_user: User) -> None:
        with pytest.raises(InvalidNameError):
            valid_user.change_name("Ana", "")

    def test_deactivate_marca_como_inativo(self, valid_user: User) -> None:
        assert valid_user.is_active is True
        valid_user.deactivate()
        assert valid_user.is_active is False

    def test_activate_marca_como_ativo(self, valid_user: User) -> None:
        valid_user.deactivate()
        valid_user.activate()
        assert valid_user.is_active is True

    def test_mutacao_preserva_created_at(self, valid_user: User) -> None:
        created_original = valid_user.created_at
        valid_user.change_email(Email("outro@example.com"))
        valid_user.deactivate()
        assert valid_user.created_at == created_original
