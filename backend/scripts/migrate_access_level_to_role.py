"""Migração de dados da US-27: access_level de lista de UUIDs → enum Role.

Contexto
--------
Antes da US-27, ``user.access_level`` era uma lista de UUIDs que referenciavam
a tabela de catálogo ``access_level`` (títulos "admin"/"user"). A US-27 troca
esse modelo por um papel único (enum ``Role``: PARTICIPANT/MANAGER/ADMIN).

Este script percorre a tabela ``user`` no DynamoDB e reescreve o campo
``access_level`` de cada registro antigo (lista) para o valor do enum,
aplicando a regra "maior papel vence": ADMIN > MANAGER > PARTICIPANT.

Mapeamento de UUIDs legados (uuidv5(NAMESPACE_DNS, título), igual ao seed
do Terraform e ao stub dos testes):
    - uuidv5(DNS, "admin") → ADMIN
    - uuidv5(DNS, "user")  → PARTICIPANT
    (não havia "manager" no catálogo antigo.)

Características:
    - **Idempotente**: registros já no formato novo (string) são ignorados.
    - **Dry-run por padrão**: nada é gravado sem ``--apply``.
    - Endpoint do DynamoDB vem de ``--endpoint-url`` ou de ``AWS_ENDPOINT_URL``
      (mesma convenção do app), permitindo rodar contra LocalStack ou AWS.

Uso:
    python -m scripts.migrate_access_level_to_role            # dry-run
    python -m scripts.migrate_access_level_to_role --apply    # grava
"""

from __future__ import annotations

import argparse
import os
import uuid
from typing import Any

import boto3

from app.domain.access_level import Role

# UUIDs legados do catálogo (espelham o seed do Terraform).
_ADMIN_UUID = str(uuid.uuid5(uuid.NAMESPACE_DNS, "admin"))
_USER_UUID = str(uuid.uuid5(uuid.NAMESPACE_DNS, "user"))

# Precedência para a regra "maior papel vence".
_PRECEDENCE = [Role.ADMIN, Role.MANAGER, Role.PARTICIPANT]


def resolve_role(legacy_access_level: list[str]) -> Role:
    """Mapeia uma lista de UUIDs legados para um único Role (maior vence).

    UUIDs desconhecidos são ignorados; lista vazia ou só com órfãos vira
    PARTICIPANT (padrão seguro — nunca eleva privilégio por dessincronia).
    """
    roles: set[Role] = set()
    for level_id in legacy_access_level:
        if level_id == _ADMIN_UUID:
            roles.add(Role.ADMIN)
        elif level_id == _USER_UUID:
            roles.add(Role.PARTICIPANT)
    for role in _PRECEDENCE:
        if role in roles:
            return role
    return Role.PARTICIPANT


def migrate(table_name: str, endpoint_url: str | None, apply: bool) -> int:
    """Percorre a tabela e migra os registros antigos. Retorna a contagem migrada."""
    ddb = boto3.resource("dynamodb", endpoint_url=endpoint_url, region_name="us-east-1")
    table = ddb.Table(table_name)

    migrated = 0
    skipped = 0
    scan_kwargs: dict[str, Any] = {}
    while True:
        resp = table.scan(**scan_kwargs)
        for item in resp.get("Items", []):
            current = item.get("access_level")
            if not isinstance(current, list):
                # Já está no formato novo (string) ou ausente — idempotente.
                skipped += 1
                continue

            new_role = resolve_role([str(x) for x in current])
            print(
                f"  {item['id']}: {current!r} → {new_role.value}"
                + ("" if apply else "  (dry-run)")
            )
            if apply:
                table.update_item(
                    Key={"id": item["id"]},
                    UpdateExpression="SET access_level = :r",
                    ExpressionAttributeValues={":r": new_role.value},
                )
            migrated += 1

        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break
        scan_kwargs["ExclusiveStartKey"] = last_key

    print(
        f"\n{'Migrados' if apply else 'A migrar'}: {migrated} | "
        f"já no formato novo: {skipped}"
    )
    return migrated


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table", default=os.getenv("DYNAMODB_TABLE_USERS", "user"))
    parser.add_argument("--endpoint-url", default=os.getenv("AWS_ENDPOINT_URL"))
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Grava as mudanças. Sem esta flag, apenas mostra o que faria.",
    )
    args = parser.parse_args()

    print(
        f"Migrando access_level → Role na tabela '{args.table}' "
        f"({args.endpoint_url or 'AWS'})\n"
    )
    migrate(table_name=args.table, endpoint_url=args.endpoint_url, apply=args.apply)


if __name__ == "__main__":
    main()
