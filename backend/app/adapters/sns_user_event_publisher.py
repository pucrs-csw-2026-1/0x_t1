from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import boto3

from app.domain.user import User
from app.ports.user_event_publisher import UserEventPublisher

if TYPE_CHECKING:
    # Type stub do boto3 — disponível em requirements-dev.txt
    # (boto3-stubs[sns]) mas não em requirements.txt. Carregado apenas
    # durante type-check para não exigir o stub em runtime de produção.
    from mypy_boto3_sns.client import SNSClient

_EVENT_TYPE = "UserProfileChanged"


class SnsUserEventPublisher(UserEventPublisher):
    """Publica eventos de usuário num tópico SNS (fan-out para consumidores).

    O payload é um *fat event*: carrega a demografia e o papel inline, para
    que consumidores (ex.: Metrics) não precisem chamar o Auth de volta.
    """

    def __init__(
        self,
        topic_arn: str,
        endpoint_url: str | None = None,
        region_name: str = "us-east-1",
        client: SNSClient | None = None,
    ) -> None:
        self._topic_arn = topic_arn
        self._client: SNSClient = client or boto3.client(
            "sns", endpoint_url=endpoint_url, region_name=region_name
        )

    def publish_profile_changed(self, user: User) -> None:
        message = self._to_message(user)
        self._client.publish(
            TopicArn=self._topic_arn,
            Message=json.dumps(message),
            MessageAttributes={
                "event_type": {"DataType": "String", "StringValue": _EVENT_TYPE},
            },
        )

    @staticmethod
    def _to_message(user: User) -> dict[str, Any]:
        return {
            "event_type": _EVENT_TYPE,
            "user_id": user.id,
            "age": user.age,
            "area": user.area,
            "gender": user.gender.value if user.gender is not None else None,
            "city": user.city,
            "access_level": user.access_level.value,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        }
