"""Testes do adapter SnsUserEventPublisher (US-29).

O client boto3 é substituído por um spy (MagicMock) para verificar o contrato
de publicação: tópico de destino, payload JSON e atributos da mensagem — sem
depender de um SNS real.
"""

import json
from unittest.mock import MagicMock

from app.adapters.sns_user_event_publisher import SnsUserEventPublisher
from app.domain.access_level import Role
from app.domain.user import Email, Gender, HashedPassword, User, Username

_TOPIC = "arn:aws:sns:us-east-1:000000000000:user-events"


def _user(**overrides: object) -> User:
    base: dict[str, object] = {
        "username": Username("maria.silva"),
        "email": Email("maria@example.com"),
        "hashed_password": HashedPassword("$2b$12$abcdefghijklmnopqrstuv"),
        "first_name": "Maria",
        "last_name": "Silva",
    }
    base.update(overrides)
    return User(**base)  # type: ignore[arg-type]


# CT-29.1: publica no tópico configurado com event_type nos atributos
def test_publish_envia_para_o_topico_com_event_type() -> None:
    client = MagicMock()
    publisher = SnsUserEventPublisher(topic_arn=_TOPIC, client=client)

    publisher.publish_profile_changed(_user())

    client.publish.assert_called_once()
    kwargs = client.publish.call_args.kwargs
    assert kwargs["TopicArn"] == _TOPIC
    assert kwargs["MessageAttributes"]["event_type"] == {
        "DataType": "String",
        "StringValue": "UserProfileChanged",
    }


# CT-29.2: payload carrega demografia, papel e user_id (fat event)
def test_publish_payload_completo() -> None:
    client = MagicMock()
    publisher = SnsUserEventPublisher(topic_arn=_TOPIC, client=client)
    user = _user(
        age=30,
        area="Tecnologia",
        gender=Gender.M,
        city="Porto Alegre",
        access_level=Role.MANAGER,
    )

    publisher.publish_profile_changed(user)

    message = json.loads(client.publish.call_args.kwargs["Message"])
    assert message["event_type"] == "UserProfileChanged"
    assert message["user_id"] == user.id
    assert message["age"] == 30
    assert message["area"] == "Tecnologia"
    assert message["gender"] == "M"
    assert message["city"] == "Porto Alegre"
    assert message["access_level"] == "MANAGER"
    assert "occurred_at" in message


# CT-29.3 (valor-limite/partição): demografia ausente vira null no payload
def test_publish_demografia_ausente_serializa_null() -> None:
    client = MagicMock()
    publisher = SnsUserEventPublisher(topic_arn=_TOPIC, client=client)

    publisher.publish_profile_changed(_user())  # sem demografia

    message = json.loads(client.publish.call_args.kwargs["Message"])
    assert message["age"] is None
    assert message["area"] is None
    assert message["gender"] is None
    assert message["city"] is None
    # cadastro público sempre PARTICIPANT
    assert message["access_level"] == "PARTICIPANT"
