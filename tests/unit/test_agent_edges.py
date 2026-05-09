"""Testes das routing functions."""
from __future__ import annotations

import random
from uuid import uuid4

from melicrowd.agents import edges
from melicrowd.agents.state import AgentState, SessionIntent
from melicrowd.personas.models import IncomeClass, Persona


def _persona(review_likelihood: float = 0.3) -> Persona:
    return Persona(
        persona_id=uuid4(),
        name="Tester",
        age=30,
        gender="F",
        location_state="SP",
        location_city="São Paulo",
        income_class=IncomeClass.B,
        occupation="Tester",
        interests=["a", "b", "c"],
        purchase_drivers=["preço", "marca"],
        price_sensitivity=0.5,
        brand_loyalty=0.5,
        risk_tolerance=0.5,
        digital_savviness=0.7,
        avg_session_duration_min=15,
        weekly_visit_frequency=3,
        preferred_categories=["x"],
        abandonment_likelihood=0.5,
        review_likelihood=review_likelihood,
    )


def test_route_after_decide_session_with_intent() -> None:
    s = AgentState(persona=_persona(), session_intent=SessionIntent.PURCHASE)
    assert edges.route_after_decide_session(s) == "auth"


def test_route_after_decide_session_no_intent_abandons() -> None:
    s = AgentState(persona=_persona())
    assert edges.route_after_decide_session(s) == "abandon"


def test_route_after_evaluate_item_add() -> None:
    s = AgentState(persona=_persona(), last_evaluation="add_to_cart")
    assert edges.route_after_evaluate_item(s) == "add_to_cart"


def test_route_after_evaluate_item_exit_abandons() -> None:
    s = AgentState(persona=_persona(), last_evaluation="exit")
    assert edges.route_after_evaluate_item(s) == "abandon"


def test_route_after_evaluate_item_too_many_views_abandons() -> None:
    from melicrowd.agents.state import Product

    s = AgentState(persona=_persona(), last_evaluation="back_to_list")
    s.viewed_products = [f"p{i}" for i in range(10)]
    s.candidate_products = [
        Product(product_id="x", title="t", category="c", price=1.0, brand="b", rating=4.0, review_count=1)
    ]
    assert edges.route_after_evaluate_item(s) == "abandon"


def test_route_after_evaluate_item_empty_catalog_abandons() -> None:
    s = AgentState(persona=_persona(), last_evaluation="back_to_list")
    s.candidate_products = []
    assert edges.route_after_evaluate_item(s) == "abandon"


def test_route_after_continue_checkout() -> None:
    s = AgentState(persona=_persona(), last_continue_decision="checkout")
    assert edges.route_after_continue_or_checkout(s) == "checkout"


def test_route_after_checkout_pay() -> None:
    s = AgentState(persona=_persona(), last_checkout_decision="pay")
    assert edges.route_after_checkout_decision(s) == "pay"


def test_route_after_checkout_abandon() -> None:
    s = AgentState(persona=_persona(), last_checkout_decision="abandon")
    assert edges.route_after_checkout_decision(s) == "abandon"


def test_route_after_pay_review_when_likelihood_high() -> None:
    random.seed(0)
    s = AgentState(persona=_persona(review_likelihood=1.0))
    assert edges.route_after_pay(s) == "write_review"


def test_route_after_pay_skip_when_likelihood_zero() -> None:
    random.seed(0)
    s = AgentState(persona=_persona(review_likelihood=0.0))
    assert edges.route_after_pay(s) == "end"
