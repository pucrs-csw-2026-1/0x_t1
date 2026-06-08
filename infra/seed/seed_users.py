"""Seed em massa de usuários demográficos no Auth (US-17).

Gera ~25k usuários com ids determinísticos ``user_{idx:04d}_{seq:04d}``
(alinhados à convenção dos attendants do seed do Metrics) e demografia, grava
**direto** na tabela ``user`` via ``BatchWriteItem`` (id explícito + senha
placeholder — ``register`` geraria uuid e rodaria bcrypt 25k vezes), e publica
uma **amostra** de ``UserProfileChanged`` no tópico ``user-events`` para
exercitar o caminho Auth → ``user-profile`` do Metrics.

Esses usuários são **portadores de demografia**, não usuários de login: a senha
é um placeholder e nunca autentica.

Uso (com a Ministack do Auth no ar):
    python seed_users.py

Variáveis de ambiente (opcionais, com defaults):
    AWS_ENDPOINT_URL / DYNAMODB_ENDPOINT_URL  http://localhost:4566
    AWS_REGION                                us-east-1
    AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY test
    DYNAMODB_TABLE_USERS                      user
    SNS_USER_EVENTS_TOPIC_ARN                 (ARN do tópico user-events)
    AUTH_SEED_NUM_EVENTS                      50
    AUTH_SEED_PROFILE_SAMPLE                  200  (qtos UserProfileChanged publicar)
    AUTH_SEED_FORCE                           0    (1/true p/ reseedar já populado)

Idempotência: se ``user_0000_0000`` já existir, o seed é pulado — exceto se
``AUTH_SEED_FORCE`` estiver setado.
"""

from __future__ import annotations

import json
import os
import random
import sys
from datetime import UTC, datetime
from typing import Any

import boto3

NUM_EVENTS = int(os.environ.get("AUTH_SEED_NUM_EVENTS", "50"))
PROFILE_SAMPLE = int(os.environ.get("AUTH_SEED_PROFILE_SAMPLE", "200"))
RANDOM_SEED = 42

# Distribuições espelham o seed demográfico do Metrics (mesmas faixas/valores),
# agora com a origem real no Auth. Gender usa os valores do enum do domínio.
ATTENDANTS_PER_EVENT_MIN = 300
ATTENDANTS_PER_EVENT_MAX = 700
GENDERS = ["F", "M", "OUTRO", "NAO_INFORMADO"]
ACCESS_LEVELS = ["PARTICIPANT", "MANAGER", "ADMIN"]
ACCESS_WEIGHTS = [90, 8, 2]
CITIES = ["Porto Alegre", "Curitiba", "São Paulo", "Rio de Janeiro", "Florianópolis"]
AREAS = ["TI", "Saúde", "Educação", "Engenharia", "Direito"]

# Senha placeholder: estes usuários carregam demografia, não autenticam.
# `HashedPassword` exige apenas valor não-vazio; o login nunca é exercido.
PLACEHOLDER_PASSWORD_HASH = "!seed-demographic-no-login!"

_EVENT_TYPE = "UserProfileChanged"


def _ddb_client() -> Any:
    endpoint = os.environ.get("AWS_ENDPOINT_URL") or os.environ.get(
        "DYNAMODB_ENDPOINT_URL", "http://localhost:4566"
    )
    return boto3.client(
        "dynamodb",
        endpoint_url=endpoint,
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
    )


def _sns_client() -> Any:
    endpoint = os.environ.get("AWS_ENDPOINT_URL") or os.environ.get(
        "DYNAMODB_ENDPOINT_URL", "http://localhost:4566"
    )
    return boto3.client(
        "sns",
        endpoint_url=endpoint,
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
    )


def gen_demographics(rng: random.Random) -> dict[str, Any]:
    """Sorteia demografia (função pura dado o rng — testável)."""
    return {
        "age": rng.randint(18, 65),
        "area": rng.choice(AREAS),
        "gender": rng.choice(GENDERS),
        "city": rng.choice(CITIES),
        "access_level": rng.choices(ACCESS_LEVELS, weights=ACCESS_WEIGHTS)[0],
    }


def build_user_item(
    idx: int, seq: int, demo: dict[str, Any], now_iso: str
) -> dict[str, Any]:
    """Monta o item DynamoDB (low-level) de um usuário do Auth (testável)."""
    user_id = f"user_{idx:04d}_{seq:04d}"
    return {
        "id": {"S": user_id},
        "email": {"S": f"{user_id}@seed.local"},
        "username": {"S": user_id},
        "hashed_password": {"S": PLACEHOLDER_PASSWORD_HASH},
        "first_name": {"S": "Seed"},
        "last_name": {"S": f"User {idx:04d}-{seq:04d}"},
        "access_level": {"S": demo["access_level"]},
        "is_active": {"BOOL": True},
        "created_at": {"S": now_iso},
        "updated_at": {"S": now_iso},
        "age": {"N": str(demo["age"])},
        "area": {"S": demo["area"]},
        "gender": {"S": demo["gender"]},
        "city": {"S": demo["city"]},
    }


def build_profile_message(user_id: str, demo: dict[str, Any], occurred_at: str) -> str:
    """Monta o corpo JSON de um UserProfileChanged (fat event — testável).

    Espelha ``SnsUserEventPublisher._to_message``.
    """
    return json.dumps(
        {
            "event_type": _EVENT_TYPE,
            "user_id": user_id,
            "age": demo["age"],
            "area": demo["area"],
            "gender": demo["gender"],
            "city": demo["city"],
            "access_level": demo["access_level"],
            "occurred_at": occurred_at,
        }
    )


def _is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in ("1", "true", "yes", "on")


def _already_seeded(client: Any, table_name: str) -> bool:
    """True se o usuário-sentinela ``user_0000_0000`` já existir."""
    resp = client.get_item(TableName=table_name, Key={"id": {"S": "user_0000_0000"}})
    return "Item" in resp


def _batch_put(client: Any, table_name: str, items: list[dict]) -> int:
    """Insere items em batches de 25 (limite do BatchWriteItem). Retorna total."""
    inserted = 0
    for i in range(0, len(items), 25):
        chunk = items[i : i + 25]
        client.batch_write_item(
            RequestItems={
                table_name: [{"PutRequest": {"Item": item}} for item in chunk]
            }
        )
        inserted += len(chunk)
    return inserted


def _topic_arn(sns: Any) -> str:
    arn = os.environ.get(
        "SNS_USER_EVENTS_TOPIC_ARN", "arn:aws:sns:us-east-1:000000000000:user-events"
    )
    # create_topic é idempotente: garante o tópico e devolve o ARN existente.
    name = arn.rsplit(":", 1)[-1]
    return str(sns.create_topic(Name=name)["TopicArn"])


def main() -> int:
    rng = random.Random(RANDOM_SEED)
    client = _ddb_client()
    table = os.environ.get("DYNAMODB_TABLE_USERS", "user")

    force = _is_truthy(os.environ.get("AUTH_SEED_FORCE"))
    if not force and _already_seeded(client, table):
        print(
            f"[seed-users] tabela '{table}' já tem usuários demográficos — pulando "
            f"(use AUTH_SEED_FORCE=1 para reseedar)",
            file=sys.stderr,
        )
        return 0

    now_iso = datetime.now(UTC).isoformat()
    items: list[dict[str, Any]] = []
    sample: list[tuple[str, dict[str, Any]]] = []
    for idx in range(NUM_EVENTS):
        count = rng.randint(ATTENDANTS_PER_EVENT_MIN, ATTENDANTS_PER_EVENT_MAX)
        for seq in range(count):
            demo = gen_demographics(rng)
            item = build_user_item(idx, seq, demo, now_iso)
            items.append(item)
            if len(sample) < PROFILE_SAMPLE:
                sample.append((item["id"]["S"], demo))

    inserted = _batch_put(client, table, items)
    print(
        f"[seed-users] {inserted} usuários gravados na tabela '{table}'",
        file=sys.stderr,
    )

    sns = _sns_client()
    arn = _topic_arn(sns)
    topic_name = arn.rsplit(":", 1)[-1]
    published = 0
    for user_id, demo in sample:
        sns.publish(
            TopicArn=arn,
            Message=build_profile_message(user_id, demo, datetime.now(UTC).isoformat()),
            MessageAttributes={
                "event_type": {"DataType": "String", "StringValue": _EVENT_TYPE},
            },
        )
        published += 1
    print(
        f"[seed-users] {published} UserProfileChanged publicados em '{topic_name}'",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
