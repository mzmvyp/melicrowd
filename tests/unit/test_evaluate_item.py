"""Testes do nó híbrido ``evaluate_item`` (score LLM × amostragem procedural).

A propriedade central sob teste: o fator de interesse é CENTRADO em 1.0
(interest=0.5 → mesma taxa do procedural puro) e monotônico — interesse alto
aumenta a probabilidade de add, interesse baixo diminui, sem deslocar a média
agregada para fora da banda calibrada.
"""
from __future__ import annotations

import random
from uuid import uuid4

from melicrowd.agents.nodes.evaluate_item import (
    EvaluateItemScore,
    _interest_factor,
    _sample_decision,
    _score_fallback,
)
from melicrowd.agents.state import AgentState, Product, SessionIntent
from melicrowd.personas.models import IncomeClass, Persona


def _persona(**kw: object) -> Persona:
    base: dict[str, object] = {
        "persona_id": uuid4(),
        "name": "Tester",
        "age": 30,
        "gender": "F",
        "location_state": "SP",
        "location_city": "São Paulo",
        "income_class": IncomeClass.B,
        "occupation": "Tester",
        "interests": ["a", "b", "c"],
        "purchase_drivers": ["preço", "marca"],
        "price_sensitivity": 0.5,
        "brand_loyalty": 0.5,
        "risk_tolerance": 0.5,
        "digital_savviness": 0.8,
        "avg_session_duration_min": 15,
        "weekly_visit_frequency": 3,
        "preferred_categories": ["x"],
        "abandonment_likelihood": 0.5,
        "review_likelihood": 0.3,
    }
    base.update(kw)
    return Persona(**base)  # type: ignore[arg-type]


def _state(intent: SessionIntent = SessionIntent.PURCHASE) -> AgentState:
    # Produto "neutro": rating 4.0 / 100 reviews não dispara nenhuma modulação
    # (nem penalidade de rating < 3.5 nem boost de social proof > 4.5/500).
    product = Product(
        product_id="p-1",
        title="Produto Neutro",
        price=500.0,
        category="eletrônicos",
        brand="Marca",
        rating=4.0,
        review_count=100,
        stock=10,
    )
    return AgentState(
        persona=_persona(),
        session_intent=intent,
        budget_brl=5000.0,
        current_product=product,
    )


def _add_rate(state: AgentState, interest: float | None, n: int = 6000) -> float:
    adds = sum(
        1
        for _ in range(n)
        if _sample_decision(state, interest=interest).decision == "add_to_cart"
    )
    return adds / n


def test_interest_factor_centered_and_bounded() -> None:
    # Quadrático 0.4 + 1.2·i² — centro na média EMPÍRICA do interest do LLM
    # (~0.707 → fator 1.0), medida em produção (catálogo com ratings 3.8-4.9).
    assert abs(_interest_factor(0.7071) - 1.0) < 0.01
    assert _interest_factor(0.0) == 0.4
    assert abs(_interest_factor(1.0) - 1.6) < 1e-9
    # Fora do range é clampado, nunca extrapola.
    assert _interest_factor(-1.0) == 0.4
    assert abs(_interest_factor(2.0) - 1.6) < 1e-9


def test_score_fallback_is_neutral() -> None:
    # 0.7 ≈ centro do fator → fallback não desloca a calibração.
    score = _score_fallback(_state())
    assert score.interest_level == 0.7
    assert abs(_interest_factor(score.interest_level) - 1.0) < 0.02


def test_neutral_interest_matches_procedural_rate() -> None:
    """interest≈centro (fator ~1.0) deve ter taxa ≈ procedural puro (None)."""
    random.seed(42)
    rate_neutral = _add_rate(_state(), interest=0.7071, n=12000)
    random.seed(42)
    rate_procedural = _add_rate(_state(), interest=None, n=12000)
    assert abs(rate_neutral - rate_procedural) < 0.02


def test_interest_modulates_monotonic() -> None:
    """Interesse alto > médio > baixo, nas proporções do fator 0.4-1.6×."""
    random.seed(7)
    low = _add_rate(_state(), interest=0.2)
    random.seed(7)
    mid = _add_rate(_state(), interest=0.7)
    random.seed(7)
    high = _add_rate(_state(), interest=1.0)
    assert low < mid < high
    # base purchase=0.27 → low ≈ 0.27*0.45=0.12, mid ≈ 0.27*0.99=0.27,
    # high ≈ 0.27*1.6=0.43
    assert 0.08 < low < 0.17
    assert 0.22 < mid < 0.32
    assert 0.37 < high < 0.49


def test_browse_intent_stays_in_low_band() -> None:
    """browse com interest neutro fica na banda baixa (~1.5% por produto)."""
    random.seed(11)
    rate = _add_rate(_state(SessionIntent.BROWSE), interest=0.5, n=12000)
    assert rate < 0.035


def test_score_model_validates_range() -> None:
    score = EvaluateItemScore(interest_level=0.73, reasoning="bate categoria e budget")
    assert 0.0 <= score.interest_level <= 1.0
