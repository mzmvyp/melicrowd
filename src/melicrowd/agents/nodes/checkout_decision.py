"""Nó Qwen #3: ``checkout_decision`` — decide pagar ou abandonar.

**Híbrido (score LLM × amostragem procedural)** — mesma receita do
``evaluate_item``. Histórico do tudo-ou-nada AQUI: com o prompt original o
Qwen devolvia "abandon" ~100% (conversion zero); após recalibrar o prompt
("DEFAULT = pay"), passou a devolver "pay" 9/9 = 100% (conversion de sessão
foi a 11%, alvo 3-8%). LLM em temperatura baixa não sorteia — colapsa na moda
do prompt, em qualquer direção que o prompt aponte.

Solução: o Qwen pontua ``pay_confidence`` 0-1 (vontade de concluir, juízo
qualitativo sobre carrinho × budget × persona) e o procedural calibrado
amostra a decisão, com a confidence como modulador (fator 0.4-1.6× centrado
na média empírica ~0.7). Fallback neutro (0.7) preserva a calibração.
"""
from __future__ import annotations

import random
from typing import Literal

from pydantic import BaseModel, Field

from melicrowd.agents.prompts import CHECKOUT_DECISION
from melicrowd.agents.qwen_runner import qwen_trace_fields, run_qwen_node
from melicrowd.agents.state import AgentState, NodeUpdate
from melicrowd.config import settings


class CheckoutScore(BaseModel):
    """Resposta do Qwen: APENAS a vontade de pagar (sem decisão binária)."""

    pay_confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""


class CheckoutDecisionResponse(BaseModel):
    """Decisão final do nó (amostrada proceduralmente)."""

    decision: Literal["pay", "abandon"]
    reasoning: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


def _score_fallback(_state: AgentState) -> CheckoutScore:
    """Confidence neutra quando Qwen falha — fator ~1.0, calibração intacta."""
    return CheckoutScore(pay_confidence=0.7, reasoning="fallback neutro (qwen indisponível)")


def _confidence_factor(confidence: float) -> float:
    """Mapeia confidence 0-1 → fator 0.4-1.6, centrado em ~0.7 (quadrático).

    Mesmo mapeamento do ``evaluate_item``: ``0.4 + 1.2·c²`` → f(0.707)=1.0.
    """
    c = max(0.0, min(1.0, confidence))
    return 0.4 + 1.2 * c * c


def _sample_decision(
    state: AgentState, *, confidence: float | None = None
) -> CheckoutDecisionResponse:
    """Amostra pagar/abandonar: procedural calibrado × confidence do LLM.

    Calibração base (~30-55% pay no checkout — realista BR): quem chegou aqui
    já filtrou muito, mas abandono de carrinho segue alto (60-80% da sessão).
    """
    p = state.persona
    cart_total = state.cart_total()
    # Só conta over_budget se passar BEM do orçamento (>30%), não margem fina.
    over_budget = state.budget_brl is not None and cart_total > state.budget_brl * 1.3

    factor = 1.0 if confidence is None else _confidence_factor(confidence)

    if over_budget:
        # Mesmo over_budget, ~15% paga ("queria muito") — modulado pelo LLM.
        prob_pay = min(0.5, 0.15 * factor)
        reasoning = "over_budget"
    else:
        # Probabilidade base de pagar — calibrada para 25-45 % de conversão de checkout.
        base = 0.55  # quem chegou no checkout JÁ filtrou muito
        if state.session_intent and state.session_intent.value == "purchase":
            base += 0.20  # quem entrou pra comprar paga mais
        elif state.session_intent and state.session_intent.value == "browse":
            base -= 0.20  # browsers desistem mais
        # Modulação por persona — peso menor (não punir tanto).
        base -= p.abandonment_likelihood * 0.20
        base = max(0.15, min(0.90, base))
        prob_pay = max(0.05, min(0.95, base * factor))
        reasoning = f"sampled base={base:.2f} conf={confidence if confidence is not None else '-'} p={prob_pay:.2f}"

    decision: Literal["pay", "abandon"] = "pay" if random.random() < prob_pay else "abandon"
    return CheckoutDecisionResponse(
        decision=decision,
        reasoning=reasoning,
        confidence=confidence if confidence is not None else 0.5,
    )


def _fallback(state: AgentState) -> CheckoutDecisionResponse:
    """Decisão 100% procedural (sem score LLM) — caminho qwen desabilitado."""
    return _sample_decision(state, confidence=None)


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
    """Executa o nó híbrido.

    Com ``qwen_checkout_decision_enabled=true``: Qwen pontua a vontade de
    pagar e o procedural amostra a decisão (taxa calibrada). Com ``false``:
    procedural puro com fator 1.0 — mesma calibração, zero custo LLM.
    """
    confidence: float | None = None
    if settings.qwen_checkout_decision_enabled:
        score = await run_qwen_node(
            state=state,
            node_name="checkout_decision",
            prompt=_render_prompt(state),
            response_model=CheckoutScore,
            fallback=_score_fallback,
            max_output_tokens=settings.qwen_decision_max_tokens,
        )
        confidence = score.pay_confidence

    response = _sample_decision(state, confidence=confidence)
    return {
        **qwen_trace_fields(state),
        "current_page": "checkout_decision",
        "last_checkout_decision": response.decision,
    }
