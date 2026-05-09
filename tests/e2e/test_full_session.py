"""E2E: 1 sessão completa com stub MelisimClient + MemorySaver.

Não exige Melisim/Kafka/Postgres rodando — usa stubs in-process.
Valida o fluxo end-to-end do agente: persona → decisões → outcome.

Para o teste 50_agents_15min real (que exige stack viva), ver test_50_agents.py.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from melicrowd.agents.runner import run_session
from melicrowd.agents.state import SessionOutcome
from melicrowd.execution.melisim_client import StubMelisimClient, set_client
from melicrowd.personas.models import IncomeClass, Persona


def _purchase_persona() -> Persona:
    """Persona com purchase_probability alta (intent provável: purchase)."""
    return Persona(
        persona_id=uuid4(),
        name="Compradora E2E",
        age=35,
        gender="F",
        location_state="SP",
        location_city="São Paulo",
        income_class=IncomeClass.B,
        occupation="Engenheira",
        interests=["tecnologia", "casa", "viagens"],
        purchase_drivers=["qualidade", "marca"],
        price_sensitivity=0.3,
        brand_loyalty=0.7,
        risk_tolerance=0.6,
        digital_savviness=0.9,
        avg_session_duration_min=20,
        weekly_visit_frequency=2,
        preferred_categories=["tecnologia", "casa"],
        abandonment_likelihood=0.3,
        review_likelihood=0.5,
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_run_session_with_stub_completes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Roda 1 sessão com Qwen mockado e stub Melisim. Deve terminar sem crash."""
    set_client(StubMelisimClient())

    # Mock Qwen para evitar dependência de Ollama no E2E unitário.
    from melicrowd.llm import qwen_client

    async def fake_generate_json(_prompt: str, **_: object) -> qwen_client.QwenCall:
        return qwen_client.QwenCall(
            response={"session_intent": "browse", "purchase_probability": 0.2},
            raw="",
            latency_ms=50,
            attempts=1,
        )

    monkeypatch.setattr("melicrowd.agents.qwen_runner.generate_json", fake_generate_json)

    persona = _purchase_persona()
    final = await run_session(persona)

    # Garantias mínimas:
    assert final.outcome is not None
    assert final.persona.persona_id == persona.persona_id
    assert isinstance(final.outcome, SessionOutcome)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_run_session_decision_trace_populated(monkeypatch: pytest.MonkeyPatch) -> None:
    """Garante que o trace registra pelo menos 1 chamada Qwen."""
    set_client(StubMelisimClient())

    from melicrowd.llm import qwen_client

    async def fake_generate_json(_prompt: str, **_: object) -> qwen_client.QwenCall:
        return qwen_client.QwenCall(
            response={"session_intent": "purchase", "purchase_probability": 0.8, "budget_brl": 500.0},
            raw="",
            latency_ms=50,
            attempts=1,
        )

    monkeypatch.setattr("melicrowd.agents.qwen_runner.generate_json", fake_generate_json)
    final = await run_session(_purchase_persona())

    # Pelo menos decide_session foi chamado.
    assert final.qwen_calls_count >= 1
    assert any(d.node == "decide_session" for d in final.decision_trace)
