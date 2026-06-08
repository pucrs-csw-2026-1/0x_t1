"""Testes do seed em massa de usuários demográficos (US-17).

``seed_users.py`` vive em ``infra/seed``; carregado via importlib. Exercita as
funções puras (sem rede): geração de demografia, montagem do item DynamoDB,
payload do ``UserProfileChanged`` e o helper de idempotência.

Técnicas: determinismo (mesma seed → mesma saída), partição de equivalência
(valores válidos de gênero/papel; truthy), análise de valor-limite (faixa
etária; zero-padding dos ids).
"""

from __future__ import annotations

import importlib.util
import json
import random
from datetime import datetime
from pathlib import Path
from types import ModuleType

_SEED_PATH = Path(__file__).resolve().parents[2] / "infra" / "seed" / "seed_users.py"


def _load_seed() -> ModuleType:
    spec = importlib.util.spec_from_file_location("auth_seed_users", _SEED_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# gen_demographics
# ---------------------------------------------------------------------------
def test_gen_demographics_deterministico() -> None:
    seed = _load_seed()
    a = seed.gen_demographics(random.Random(7))
    b = seed.gen_demographics(random.Random(7))
    assert a == b  # mesma seed → mesma demografia


def test_gen_demographics_valores_validos() -> None:
    seed = _load_seed()
    rng = random.Random(42)
    for _ in range(200):
        demo = seed.gen_demographics(rng)
        assert demo["gender"] in seed.GENDERS
        assert demo["access_level"] in seed.ACCESS_LEVELS
        assert demo["area"] in seed.AREAS
        assert demo["city"] in seed.CITIES
        assert 18 <= demo["age"] <= 65  # valor-limite das idades


# ---------------------------------------------------------------------------
# build_user_item
# ---------------------------------------------------------------------------
def test_build_user_item_shape_e_id_zero_padded() -> None:
    seed = _load_seed()
    demo = {
        "age": 30,
        "area": "TI",
        "gender": "F",
        "city": "Curitiba",
        "access_level": "MANAGER",
    }
    item = seed.build_user_item(3, 7, demo, "2026-06-08T00:00:00+00:00")

    assert item["id"]["S"] == "user_0003_0007"
    assert item["email"]["S"] == "user_0003_0007@seed.local"
    assert item["username"]["S"] == "user_0003_0007"
    assert item["access_level"]["S"] == "MANAGER"
    assert item["age"]["N"] == "30"
    assert item["gender"]["S"] == "F"
    assert item["city"]["S"] == "Curitiba"
    assert item["is_active"]["BOOL"] is True
    assert item["hashed_password"]["S"]  # placeholder não-vazio


# ---------------------------------------------------------------------------
# build_profile_message
# ---------------------------------------------------------------------------
def test_build_profile_message_schema() -> None:
    seed = _load_seed()
    demo = {
        "age": 22,
        "area": "Engenharia",
        "gender": "M",
        "city": "Porto Alegre",
        "access_level": "PARTICIPANT",
    }
    body = json.loads(
        seed.build_profile_message("user_0001_0002", demo, "2026-06-08T12:00:00+00:00")
    )
    assert body["event_type"] == "UserProfileChanged"
    assert body["user_id"] == "user_0001_0002"
    assert body["age"] == 22
    assert body["gender"] == "M"
    assert body["access_level"] == "PARTICIPANT"
    assert datetime.fromisoformat(body["occurred_at"])


# ---------------------------------------------------------------------------
# _is_truthy (partição + valor-limite)
# ---------------------------------------------------------------------------
def test_is_truthy() -> None:
    seed = _load_seed()
    for v in ("1", "true", "TRUE", "yes", "on", " On "):
        assert seed._is_truthy(v) is True
    for v in ("", None, "0", "false", "no", "off"):
        assert seed._is_truthy(v) is False
