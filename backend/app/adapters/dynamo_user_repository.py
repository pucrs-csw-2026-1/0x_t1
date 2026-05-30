from __future__ import annotations

import os
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

import boto3
from botocore.exceptions import ClientError

from app.domain.user import Email, Gender, HashedPassword, User, Username
from app.ports.user_repository import UserPage, UserRepository

if TYPE_CHECKING:
    # Type stubs do boto3 — disponíveis em requirements-dev.txt
    # (mypy-boto3-dynamodb) mas não em requirements.txt. Carregar apenas
    # durante type-check evita ModuleNotFoundError em runtime quando a
    # aplicação roda em container com apenas as deps de produção.
    from mypy_boto3_dynamodb.service_resource import Table


class DynamoUserRepository(UserRepository):
    def __init__(
        self,
        table_name: str = "user",
        endpoint_url: str | None = None,
        auto_create: bool = False,
    ) -> None:
        endpoint_url = endpoint_url or os.getenv("DYNAMODB_ENDPOINT_URL")
        self._client = boto3.resource(
            "dynamodb", endpoint_url=endpoint_url, region_name="us-east-1"
        )
        if auto_create:
            self._ensure_table(table_name)
        self._table: Table = self._client.Table(table_name)

    def save(self, user: User) -> User:
        self._table.put_item(Item=self._to_item(user))
        return user

    def find_by_id(self, id: str) -> User | None:
        response = self._table.get_item(Key={"id": id})
        item = response.get("Item")
        return self._to_user(item) if item else None

    def find_by_email(self, email: Email) -> User | None:
        resp = self._table.query(
            IndexName="email-index",
            KeyConditionExpression="email = :e",
            ExpressionAttributeValues={":e": email.value},
        )
        items = resp.get("Items", [])
        return self._to_user(items[0]) if items else None

    def find_by_username(self, username: Username) -> User | None:
        resp = self._table.query(
            IndexName="username-index",
            KeyConditionExpression="username = :u",
            ExpressionAttributeValues={":u": username.value},
        )
        items = resp.get("Items", [])
        return self._to_user(items[0]) if items else None

    def find_all(self, limit: int, cursor: str | None = None) -> UserPage:
        scan_kwargs: dict[str, Any] = {"Limit": limit}
        if cursor is not None:
            scan_kwargs["ExclusiveStartKey"] = {"id": cursor}
        resp = self._table.scan(**scan_kwargs)
        items = [self._to_user(it) for it in resp.get("Items", [])]
        last_key = resp.get("LastEvaluatedKey")
        next_cursor = cast(str, last_key["id"]) if last_key else None
        return UserPage(items=items, next_cursor=next_cursor)

    def _to_item(self, user: User) -> dict[str, Any]:
        item: dict[str, Any] = {
            "id": user.id,
            "email": user.email.value,
            "username": user.username.value,
            "hashed_password": user.hashed_password.value,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "access_level": user.access_level,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat(),
            "updated_at": user.updated_at.isoformat(),
        }
        # Campos demográficos opcionais: omitidos do item quando ausentes
        # para não gravar atributos NULL no DynamoDB.
        if user.age is not None:
            item["age"] = user.age
        if user.area is not None:
            item["area"] = user.area
        if user.gender is not None:
            item["gender"] = user.gender.value
        if user.city is not None:
            item["city"] = user.city
        return item

    def _to_user(self, item: dict[str, Any]) -> User:
        # DynamoDB devolve números como Decimal; converte idade de volta a int.
        raw_age = item.get("age")
        raw_gender = item.get("gender")
        return User(
            id=item["id"],
            email=Email(item["email"]),
            username=Username(item["username"]),
            hashed_password=HashedPassword(item["hashed_password"]),
            first_name=item["first_name"],
            last_name=item["last_name"],
            age=int(raw_age) if raw_age is not None else None,
            area=item.get("area"),
            gender=Gender(raw_gender) if raw_gender is not None else None,
            city=item.get("city"),
            access_level=item.get("access_level", []),
            is_active=bool(item.get("is_active", True)),
            created_at=datetime.fromisoformat(item["created_at"]),
            updated_at=datetime.fromisoformat(item["updated_at"]),
        )

    def _ensure_table(self, table_name: str) -> None:
        try:
            self._client.meta.client.describe_table(TableName=table_name)
            return
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                raise
        table = self._client.create_table(
            TableName=table_name,
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "id", "AttributeType": "S"},
                {"AttributeName": "email", "AttributeType": "S"},
                {"AttributeName": "username", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "email-index",
                    "KeySchema": [{"AttributeName": "email", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "username-index",
                    "KeySchema": [{"AttributeName": "username", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
