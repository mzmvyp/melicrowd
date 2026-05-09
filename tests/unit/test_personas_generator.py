"""Testes do generator de personas com Qwen mockado."""
from __future__ import annotations

from typing import Any

import pytest

from melicrowd.llm import qwen_client
from melicrowd.personas import generator
from melicrowd.personas.generator import (
    distribution_within_tolerance,
    generate_batch,
)
from melicrowd.personas.models import IncomeClass, Persona


def _qwen_response(income_class: str = "B", name: str = "Persona Test") -> dict[str, Any]:
    return {
        "name": name,
        "age": 35,
        "gender": "F",
        "location_state": "SP",
        "location_city": "São Paulo",
        "income_class": income_class,
        "occupation": "Engenheira de Dados",
        "interests": ["tecnologia", "leitura", "esportes"],
        "purchase_drivers": ["qualidade", "marca"],
        "price_sensitivity": 0.4,
        "brand_loyalty": 0.7,
        "risk_tolerance": 0.5,
        "digital_savviness": 0.85,
        "avg_session_duration_min": 12,
        "weekly_visit_frequency": 5,
        "preferred_categories": ["tecnologia", "livros"],
        "abandonment_likelihood": 0.3,
        "review_likelihood": 0.5,
    }


@pytest.mark.asyncio
async def test_generate_batch_returns_requested_count(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_generate_json(_prompt: str, **_: Any) -> qwen_client.QwenCall:
        return qwen_client.QwenCall(
            response=_qwen_response(),
            raw="",
            latency_ms=10,
            attempts=1,
        )

    monkeypatch.setattr(generator, "generate_json", fake_generate_json)
    personas = await generate_batch(5)
    assert len(personas) == 5
    assert all(isinstance(p, Persona) for p in personas)


@pytest.mark.asyncio
async def test_generate_batch_zero_returns_empty() -> None:
    personas = await generate_batch(0)
    assert personas == []


@pytest.mark.asyncio
async def test_generate_batch_retries_invalid_personas(monkeypatch: pytest.MonkeyPatch) -> None:
    """Se Qwen retorna inválidos, generator tenta de novo até atingir o alvo."""
    call_count = 0

    async def flaky_generate(_prompt: str, **_: Any) -> qwen_client.QwenCall:
        nonlocal call_count
        call_count += 1
        # First 2 calls return invalid age (rejected by Pydantic); rest are valid.
        invalid = call_count <= 2
        payload = _qwen_response()
        if invalid:
            payload["age"] = 5  # below 18 → ValidationError
        return qwen_client.QwenCall(
            response=payload,
            raw="",
            latency_ms=10,
            attempts=1,
        )

    monkeypatch.setattr(generator, "generate_json", flaky_generate)
    personas = await generate_batch(3)
    assert len(personas) == 3
    assert call_count >= 3 + 2  # 3 valid + 2 invalid


def test_distribution_within_tolerance_balanced() -> None:
    # 10/30/45/15 distribution exact.
    counts = {IncomeClass.A: 1, IncomeClass.B: 3, IncomeClass.C: 5, IncomeClass.D: 1}
    personas = []
    for cls, n in counts.items():
        for _ in range(n):
            personas.append(Persona(**_qwen_response(income_class=cls.value)))  # type: ignore[arg-type]
    assert distribution_within_tolerance(personas) is True


def test_distribution_within_tolerance_skewed() -> None:
    # All class A — clearly off-target.
    personas = [Persona(**_qwen_response(income_class="A")) for _ in range(10)]  # type: ignore[arg-type]
    assert distribution_within_tolerance(personas) is False
