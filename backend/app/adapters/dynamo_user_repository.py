from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError
from mypy_boto3_dynamodb.service_resource import Table

from app.domain.user import Email, HashedPassword, User, Username
from app.ports.user_repository import UserRepository


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

    def _to_item(self, user: User) -> dict[str, Any]:
        return {
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

    def _to_user(self, item: dict[str, Any]) -> User:
        return User(
            id=item["id"],
            email=Email(item["email"]),
            username=Username(item["username"]),
            hashed_password=HashedPassword(item["hashed_password"]),
            first_name=item["first_name"],
            last_name=item["last_name"],
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
