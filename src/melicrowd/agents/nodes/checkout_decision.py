"""Nó Qwen #3: ``checkout_decision`` — decide pagar ou abandonar."""
from __future__ import annotations

import random
from typing import Literal

from pydantic import BaseModel, Field

from melicrowd.agents.prompts import CHECKOUT_DECISION
from melicrowd.agents.qwen_runner import run_qwen_node
from melicrowd.agents.state import AgentState, NodeUpdate
from melicrowd.config import settings


class CheckoutDecisionResponse(BaseModel):
    decision: Literal["pay", "abandon"]
    reasoning: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


def _fallback(state: AgentState) -> CheckoutDecisionResponse:
    """Decisão procedural calibrada (~30-40% pay, ~60-70% abandon).

    Mantém abandono alto (realista BR), mas garante que pelo menos 1/3 dos
    agentes que chegam no checkout efetivamente paguem — antes o cálculo
    de over_budget marcava quase todos como abandon e a UI mostrava 0%
    de conversion nos nós `pay`/`purchased`.
    """
    p = state.persona
    cart_total = state.cart_total()
    # Só conta over_budget se passar BEM do orçamento (>30%), não margem fina.
    over_budget = state.budget_brl is not None and cart_total > state.budget_brl * 1.3

    if over_budget:
        # Mesmo over_budget, 15% paga ("queria muito").
        decision: Literal["pay", "abandon"] = "pay" if random.random() < 0.15 else "abandon"
        reasoning = "over_budget"
    else:
        # Probabilidade base de pagar — calibrada para 25-45 % de conversão de checkout.
        base = 0.55  # default subido — quem chegou no checkout JÁ filtrou muito
        if state.session_intent and state.session_intent.value == "purchase":
            base += 0.20  # quem entrou pra comprar paga mais
        elif state.session_intent and state.session_intent.value == "browse":
            base -= 0.20  # browsers desistem mais
        # Modulação por persona — peso menor (não punir tanto).
        base -= p.abandonment_likelihood * 0.20
        base = max(0.15, min(0.90, base))
        decision = "pay" if random.random() < base else "abandon"
        reasoning = f"procedural base={base:.2f}"

    return CheckoutDecisionResponse(decision=decision, reasoning=reasoning)


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
    """Executa o nó.

    Modo default: usa fallback procedural (sem Qwen). Bench mostrou que o
    Qwen real interpreta o prompt do checkout muito conservador e devolve
    "abandon" em quase 100% dos casos — zerando conversion. Procedural
    com calibração persona+intent dá ~25-40% pay consistente.
    Ative Qwen via ``MELICROWD_QWEN_CHECKOUT_DECISION_ENABLED=true``.
    """
    if settings.qwen_checkout_decision_enabled:
        response = await run_qwen_node(
            state=state,
            node_name="checkout_decision",
            prompt=_render_prompt(state),
            response_model=CheckoutDecisionResponse,
            fallback=_fallback,
        )
    else:
        response = _fallback(state)
    return {"current_page": "checkout_decision", "last_checkout_decision": response.decision}
