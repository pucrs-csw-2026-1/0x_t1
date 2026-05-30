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

from app.domain.access_level import ROLE_SCOPES, Role, scopes_for
from app.domain.exceptions import (
    InvalidAgeError,
    InvalidEmailError,
    InvalidNameError,
    InvalidProfileFieldError,
    InvalidUsernameError,
    WeakPasswordError,
)
from app.domain.user import (
    Email,
    Gender,
    HashedPassword,
    User,
    Username,
    validate_age,
    validate_name_field,
    validate_profile_text,
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

    def test_access_level_padrao_e_participant(self, valid_user: User) -> None:
        assert valid_user.access_level is Role.PARTICIPANT

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


# ═══════════════════════════════════════════════════════════════════
# US-26 — Campos demográficos
# ═══════════════════════════════════════════════════════════════════


class TestGender:
    """Enum de gênero serializa pelo valor (str)."""

    @pytest.mark.parametrize("valor", ["F", "M", "OUTRO", "NAO_INFORMADO"])
    def test_aceita_valores_validos(self, valor: str) -> None:
        assert Gender(valor).value == valor

    def test_e_str(self) -> None:
        # str na base permite comparar/serializar pelo valor
        assert Gender.OUTRO == "OUTRO"

    def test_rejeita_valor_invalido(self) -> None:
        with pytest.raises(ValueError):
            Gender("INVALIDO")


class TestValidateAge:
    """Valores-limite: -1 (rejeita), 0 (aceita), 150 (aceita), 151 (rejeita)."""

    def test_none_e_aceito(self) -> None:
        assert validate_age(None) is None

    def test_idade_negativa_rejeita(self) -> None:
        with pytest.raises(InvalidAgeError):
            validate_age(-1)

    def test_idade_0_aceita(self) -> None:
        assert validate_age(0) == 0

    def test_idade_150_aceita(self) -> None:
        assert validate_age(150) == 150

    def test_idade_151_rejeita(self) -> None:
        with pytest.raises(InvalidAgeError):
            validate_age(151)


class TestValidateProfileText:
    """Valores-limite: 0 (rejeita), 1 (aceita), 128 (aceita), 129 (rejeita)."""

    def test_none_e_aceito(self) -> None:
        assert validate_profile_text(None, "area") is None

    def test_vazio_rejeita(self) -> None:
        with pytest.raises(InvalidProfileFieldError):
            validate_profile_text("", "area")

    def test_so_espacos_rejeita(self) -> None:
        with pytest.raises(InvalidProfileFieldError):
            validate_profile_text("   ", "city")

    def test_1_char_aceita(self) -> None:
        assert validate_profile_text("A", "area") == "A"

    def test_128_chars_aceita(self) -> None:
        valor = "a" * 128
        assert validate_profile_text(valor, "area") == valor

    def test_129_chars_rejeita(self) -> None:
        with pytest.raises(InvalidProfileFieldError):
            validate_profile_text("a" * 129, "city")

    def test_normaliza_com_strip(self) -> None:
        assert validate_profile_text("  Porto Alegre  ", "city") == "Porto Alegre"

    def test_mensagem_cita_o_campo(self) -> None:
        with pytest.raises(InvalidProfileFieldError, match="area"):
            validate_profile_text("", "area")


class TestUserDemographics:
    """Demografia opcional na entidade User (US-26)."""

    def test_campos_demograficos_default_none(self, valid_user: User) -> None:
        assert valid_user.age is None
        assert valid_user.area is None
        assert valid_user.gender is None
        assert valid_user.city is None

    def test_aceita_demografia_valida(self, valid_user_kwargs: dict[str, Any]) -> None:
        user = User(
            **valid_user_kwargs,
            age=30,
            area="Engenharia",
            gender=Gender.OUTRO,
            city="Porto Alegre",
        )
        assert user.age == 30
        assert user.area == "Engenharia"
        assert user.gender is Gender.OUTRO
        assert user.city == "Porto Alegre"

    def test_idade_invalida_na_construcao_rejeita(
        self, valid_user_kwargs: dict[str, Any]
    ) -> None:
        with pytest.raises(InvalidAgeError):
            User(**valid_user_kwargs, age=200)

    def test_area_invalida_na_construcao_rejeita(
        self, valid_user_kwargs: dict[str, Any]
    ) -> None:
        with pytest.raises(InvalidProfileFieldError):
            User(**valid_user_kwargs, area="x" * 129)

    def test_gender_string_e_coercido_para_enum(
        self, valid_user_kwargs: dict[str, Any]
    ) -> None:
        # Leitura do repositório pode entregar string crua
        user = User(**valid_user_kwargs, gender="F")
        assert user.gender is Gender.F

    def test_change_demographics_atualiza_apenas_informados(
        self, valid_user: User
    ) -> None:
        valid_user.change_demographics(age=40, gender=Gender.M)
        assert valid_user.age == 40
        assert valid_user.gender is Gender.M
        # campos não informados permanecem None
        assert valid_user.area is None
        assert valid_user.city is None

    def test_change_demographics_none_preserva_valor(
        self, valid_user_kwargs: dict[str, Any]
    ) -> None:
        user = User(**valid_user_kwargs, city="Porto Alegre")
        user.change_demographics(age=25, city=None)
        assert user.age == 25
        # city=None significa "não alterar", não "limpar"
        assert user.city == "Porto Alegre"

    def test_change_demographics_valida(self, valid_user: User) -> None:
        with pytest.raises(InvalidAgeError):
            valid_user.change_demographics(age=-5)

    def test_change_demographics_atualiza_updated_at(self, valid_user: User) -> None:
        valid_user.updated_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
        valid_user.change_demographics(age=33)
        assert valid_user.updated_at > datetime(2000, 1, 1, tzinfo=timezone.utc)


# ═══════════════════════════════════════════════════════════════════
# US-27 — Papel (Role) e scopes cumulativos
# ═══════════════════════════════════════════════════════════════════


class TestRole:
    """Enum de papel e derivação cumulativa de scopes."""

    @pytest.mark.parametrize("valor", ["PARTICIPANT", "MANAGER", "ADMIN"])
    def test_aceita_valores_validos(self, valor: str) -> None:
        assert Role(valor).value == valor

    def test_rejeita_valor_invalido(self) -> None:
        with pytest.raises(ValueError):
            Role("SUPERADMIN")

    def test_scopes_participant_apenas_base(self) -> None:
        assert scopes_for(Role.PARTICIPANT) == ["participant"]

    def test_scopes_manager_cumulativo(self) -> None:
        assert sorted(scopes_for(Role.MANAGER)) == ["manager", "participant"]

    def test_scopes_admin_cumulativo_inclui_admin(self) -> None:
        scopes = scopes_for(Role.ADMIN)
        assert sorted(scopes) == ["admin", "manager", "participant"]
        # gate de /admin/* compara 'admin' in scopes
        assert "admin" in scopes

    def test_hierarquia_e_cumulativa(self) -> None:
        # cada papel superior contém os scopes do inferior
        assert set(ROLE_SCOPES[Role.PARTICIPANT]) <= set(ROLE_SCOPES[Role.MANAGER])
        assert set(ROLE_SCOPES[Role.MANAGER]) <= set(ROLE_SCOPES[Role.ADMIN])

    def test_scopes_for_retorna_copia(self) -> None:
        # mutar o retorno não deve afetar o mapa global
        scopes = scopes_for(Role.ADMIN)
        scopes.append("hacked")
        assert "hacked" not in ROLE_SCOPES[Role.ADMIN]


class TestUserRole:
    """Papel na entidade User (US-27)."""

    def test_default_e_participant(self, valid_user: User) -> None:
        assert valid_user.access_level is Role.PARTICIPANT

    def test_coage_string_para_role(self, valid_user_kwargs: dict[str, Any]) -> None:
        # leitura do repositório entrega string crua
        user = User(**valid_user_kwargs, access_level="ADMIN")
        assert user.access_level is Role.ADMIN

    def test_string_invalida_rejeita(self, valid_user_kwargs: dict[str, Any]) -> None:
        with pytest.raises(ValueError):
            User(**valid_user_kwargs, access_level="ROOT")

    def test_change_role_altera_papel(self, valid_user: User) -> None:
        valid_user.change_role(Role.MANAGER)
        assert valid_user.access_level is Role.MANAGER

    def test_change_role_aceita_string(self, valid_user: User) -> None:
        valid_user.change_role("ADMIN")
        assert valid_user.access_level is Role.ADMIN

    def test_change_role_atualiza_updated_at(self, valid_user: User) -> None:
        valid_user.updated_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
        valid_user.change_role(Role.ADMIN)
        assert valid_user.updated_at > datetime(2000, 1, 1, tzinfo=timezone.utc)
