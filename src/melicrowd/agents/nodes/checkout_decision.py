"""Nó Qwen #3: ``checkout_decision`` — decide pagar ou abandonar."""
from __future__ import annotations

import random
from typing import Literal

from pydantic import BaseModel, Field

from melicrowd.agents.prompts import CHECKOUT_DECISION
from melicrowd.agents.qwen_runner import run_qwen_node
from melicrowd.agents.state import AgentState, NodeUpdate


class CheckoutDecisionResponse(BaseModel):
    decision: Literal["pay", "abandon"]
    reasoning: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


def _fallback(state: AgentState) -> CheckoutDecisionResponse:
    """Decisão procedural calibrada com benchmarks BR (60-80% abandono)."""
    p = state.persona
    cart_total = state.cart_total()
    over_budget = state.budget_brl is not None and cart_total > state.budget_brl * 1.1

    if over_budget:
        decision: Literal["pay", "abandon"] = "abandon"
    else:
        # Probabilidade de pagar = 1 - abandonment_likelihood, ajustado por intent.
        base = 1.0 - p.abandonment_likelihood
        if state.session_intent and state.session_intent.value == "purchase":
            base += 0.2
        decision = "pay" if random.random() < base else "abandon"

    return CheckoutDecisionResponse(decision=decision, reasoning="fallback procedural")


def _render_prompt(state: AgentState) -> str:
    p = state.persona
    return CHECKOUT_DECISION.format(
        persona_name=p.name,
        persona_age=p.age,
        income_class=p.income_class.value,
        price_sensitivity=p.price_sensitivity,
        abandonment_likelihood=p.abandonment_likelihood,
        risk_tolerance=p.risk_tolerance,
        cart_items_count=len(state.cart),
        cart_total=state.cart_total(),
        budget_brl=state.budget_brl or 0,
        stocks_ok="sim",
    )


async def run(state: AgentState) -> NodeUpdate:
    """Executa o nó."""
    response = await run_qwen_node(
        state=state,
        node_name="checkout_decision",
        prompt=_render_prompt(state),
        response_model=CheckoutDecisionResponse,
        fallback=_fallback,
    )
    return {"current_page": "checkout", "last_checkout_decision": response.decision}
