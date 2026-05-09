"""Testes do AgentState e enums."""
from __future__ import annotations

from uuid import uuid4

import pytest

from melicrowd.agents.state import (
    AgentState,
    CartItem,
    DecisionRecord,
    SessionIntent,
    SessionOutcome,
)
from melicrowd.personas.models import IncomeClass, Persona


def _persona() -> Persona:
    return Persona(
        persona_id=uuid4(),
        name="Test User",
        age=30,
        gender="F",
        location_state="SP",
        location_city="São Paulo",
        income_class=IncomeClass.B,
        occupation="Tester",
        interests=["tecnologia", "leitura", "viagens"],
        purchase_drivers=["preço", "marca"],
        price_sensitivity=0.5,
        brand_loyalty=0.5,
        risk_tolerance=0.5,
        digital_savviness=0.7,
        avg_session_duration_min=15,
        weekly_visit_frequency=3,
        preferred_categories=["tecnologia"],
        abandonment_likelihood=0.5,
        review_likelihood=0.3,
    )


def test_agent_state_initial() -> None:
    s = AgentState(persona=_persona())
    assert s.outcome is None
    assert s.cart == []
    assert s.cart_total() == 0.0
    assert s.qwen_calls_count == 0


def test_cart_total_with_items() -> None:
    s = AgentState(persona=_persona())
    s.cart.append(CartItem(product_id="p1", title="A", price=100.0, quantity=2))
    s.cart.append(CartItem(product_id="p2", title="B", price=50.0, quantity=1))
    assert s.cart_total() == 250.0


def test_record_decision_increments_counters() -> None:
    s = AgentState(persona=_persona())
    record = DecisionRecord(node="decide_session", prompt_chars=500, latency_ms=1200)
    s.record_decision(record, latency_ms=1200)
    assert s.qwen_calls_count == 1
    assert s.qwen_total_latency_ms == 1200
    assert len(s.decision_trace) == 1


def test_session_intent_enum_values() -> None:
    assert SessionIntent.PURCHASE.value == "purchase"
    assert SessionOutcome.PURCHASED.value == "purchased"
