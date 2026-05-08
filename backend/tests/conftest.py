"""Fixtures globais compartilhadas entre os testes."""

import uuid
from collections.abc import Iterator
from typing import Any

import boto3
import pytest
from moto import mock_aws

from app.adapters.dynamo_user_repository import DynamoUserRepository
from app.domain.access_level import AccessLevel
from app.domain.user import Email, HashedPassword, User, Username
from app.ports.user_repository import UserRepository
from tests.fakes.access_level_repository import FakeAccessLevelRepository
from tests.fakes.user_repository import FakeUserRepository

# UUIDs determinísticos espelhando o seed do Terraform
# (uuidv5(NAMESPACE_DNS, "admin"|"user")). Mantidos aqui para que stubs
# reproduzam o catálogo real sem depender do banco.
ADMIN_UUID = str(uuid.uuid5(uuid.NAMESPACE_DNS, "admin"))
USER_UUID = str(uuid.uuid5(uuid.NAMESPACE_DNS, "user"))


@pytest.fixture
def valid_user_kwargs() -> dict[str, Any]:
    return {
        "username": Username("maria.silva"),
        "email": Email("maria@example.com"),
        "hashed_password": HashedPassword("$2b$12$abcdefghijklmnopqrstuv"),
        "first_name": "Maria",
        "last_name": "Silva",
    }


@pytest.fixture
def valid_user(valid_user_kwargs: dict[str, Any]) -> User:
    return User(**valid_user_kwargs)


@pytest.fixture
def fake_repo() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def fake_access_level_repo() -> FakeAccessLevelRepository:
    """Catalogo padrao com admin e user, espelhando o seed do Terraform."""
    return FakeAccessLevelRepository(
        levels=[
            AccessLevel(id=ADMIN_UUID, title="admin"),
            AccessLevel(id=USER_UUID, title="user"),
        ]
    )


@pytest.fixture
def dynamo_repo() -> Iterator[DynamoUserRepository]:
    with mock_aws():
        boto3.resource("dynamodb", region_name="us-east-1").create_table(
            TableName="user",
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
        yield DynamoUserRepository(table_name="user")


@pytest.fixture(params=["fake_repo", "dynamo_repo"])
def repo(request: pytest.FixtureRequest) -> UserRepository:
    return request.getfixturevalue(request.param)
