from enum import Enum


class Role(str, Enum):
    """Papel único do usuário (eixo de privilégio).

    `str` na base para serializar/comparar pelo valor. Os papéis formam
    uma hierarquia cumulativa: ADMIN ⊇ MANAGER ⊇ PARTICIPANT — modelada na
    derivação de scope (ver ROLE_SCOPES), não no enum.
    """

    PARTICIPANT = "PARTICIPANT"
    MANAGER = "MANAGER"
    ADMIN = "ADMIN"


# Scopes do JWT por papel. Cumulativo: cada papel inclui os scopes dos
# inferiores, então um gate que exige "manager" também aceita ADMIN, e o
# gate de "admin" das rotas /admin/* continua válido para ADMIN.
ROLE_SCOPES: dict[Role, list[str]] = {
    Role.PARTICIPANT: ["participant"],
    Role.MANAGER: ["participant", "manager"],
    Role.ADMIN: ["participant", "manager", "admin"],
}


def scopes_for(role: Role) -> list[str]:
    """Retorna a lista cumulativa de scopes para o papel informado."""
    return list(ROLE_SCOPES[role])
