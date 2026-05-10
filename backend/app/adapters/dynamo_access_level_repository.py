from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import boto3

from app.domain.access_level import AccessLevel
from app.ports.access_level_repository import AccessLevelRepository

if TYPE_CHECKING:
    # Type stubs do boto3 — disponíveis em requirements-dev.txt
    # (mypy-boto3-dynamodb) mas não em requirements.txt. Carregar apenas
    # durante type-check evita ModuleNotFoundError em runtime quando a
    # aplicação roda em container com apenas as deps de produção.
    from mypy_boto3_dynamodb.service_resource import Table


class DynamoAccessLevelRepository(AccessLevelRepository):
    """Implementação de AccessLevelRepository usando DynamoDB.

    Catálogo de leitura: o seed dos perfis (`admin`, `user`) é feito
    pelo Terraform; a aplicação nunca grava nesta tabela.
    """

    def __init__(
        self,
        table_name: str = "access_level",
        endpoint_url: str | None = None,
    ) -> None:
        endpoint_url = endpoint_url or os.getenv("DYNAMODB_ENDPOINT_URL")
        self._client = boto3.resource(
            "dynamodb", endpoint_url=endpoint_url, region_name="us-east-1"
        )
        self._table: Table = self._client.Table(table_name)

    def find_by_id(self, id: str) -> AccessLevel | None:
        response = self._table.get_item(Key={"id": id})
        item = response.get("Item")
        return self._to_access_level(item) if item else None

    def find_by_title(self, title: str) -> AccessLevel | None:
        response = self._table.scan(
            FilterExpression="title = :t",
            ExpressionAttributeValues={":t": title},
        )
        items = response.get("Items", [])
        return self._to_access_level(items[0]) if items else None

    def _to_access_level(self, item: dict[str, Any]) -> AccessLevel:
        return AccessLevel(id=item["id"], title=item["title"])
