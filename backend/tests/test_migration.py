"""Testes da regra de migração access_level (UUIDs) → Role (US-27).

Cobre o ponto sensível de segurança: "maior papel vence" e o padrão seguro
(nunca elevar privilégio por dessincronia / UUID órfão)."""

from __future__ import annotations

from app.domain.access_level import Role
from scripts.migrate_access_level_to_role import (
    _ADMIN_UUID,
    _USER_UUID,
    resolve_role,
)


def test_lista_vazia_vira_participant() -> None:
    assert resolve_role([]) is Role.PARTICIPANT


def test_uuid_de_user_vira_participant() -> None:
    assert resolve_role([_USER_UUID]) is Role.PARTICIPANT


def test_uuid_de_admin_vira_admin() -> None:
    assert resolve_role([_ADMIN_UUID]) is Role.ADMIN


def test_maior_papel_vence() -> None:
    # usuário com user + admin resolve para ADMIN (independente da ordem)
    assert resolve_role([_USER_UUID, _ADMIN_UUID]) is Role.ADMIN
    assert resolve_role([_ADMIN_UUID, _USER_UUID]) is Role.ADMIN


def test_uuid_orfao_e_ignorado_com_default_seguro() -> None:
    # UUID desconhecido não eleva privilégio; sem outro papel, vira PARTICIPANT
    assert resolve_role(["uuid-desconhecido"]) is Role.PARTICIPANT
    # órfão + user → PARTICIPANT (não escala)
    assert resolve_role(["uuid-desconhecido", _USER_UUID]) is Role.PARTICIPANT
