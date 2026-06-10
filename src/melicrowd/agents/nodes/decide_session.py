"""Nó Qwen #1: ``decide_session`` — define intent + categorias + budget.

**Híbrido (sorteio procedural × contexto LLM).** Medição em produção: quando o
Qwen escolhia o intent, 53/53 sessões saíram "browse" — o mesmo tudo-ou-nada
do ``evaluate_item`` (LLM em temperatura baixa colapsa na moda da distribuição
pedida no prompt; ele não sabe "sortear a 50/33/12/5"). Solução:

1. O **intent é sorteado** proceduralmente da distribuição calibrada
   (browse 50% / research 33% / compare 12% / purchase 5%, benchmark BR),
   modulada pela persona (frequência de visita, drivers).
2. O **Qwen contextualiza** o intent sorteado: categorias-alvo, budget e
   purchase_probability coerentes com a persona — juízo qualitativo, onde o
   determinismo dele não atrapalha.
"""
from __future__ import annotations

import random
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from melicrowd.agents.prompts import DECIDE_SESSION
from melicrowd.agents.qwen_runner import qwen_trace_fields, run_qwen_node
from melicrowd.agents.state import AgentState, NodeUpdate, SessionIntent
from melicrowd.config import settings

IntentLiteral = Literal["browse", "research", "compare", "purchase"]

#: Distribuição base de intents (benchmark varejo BR — maioria navega, não compra).
_BASE_INTENT_WEIGHTS: dict[IntentLiteral, float] = {
    "browse": 0.50,
    "research": 0.33,
    "compare": 0.12,
    "purchase": 0.05,
}


class DecideSessionContext(BaseModel):
    """Resposta do Qwen: contexto da visita (o intent já vem sorteado)."""

    target_categories: list[str] = Field(default_factory=list)
    budget_brl: float | None = None
    purchase_probability: float = Field(ge=0.0, le=1.0, default=0.3)
    reasoning: str = ""


def _sample_intent(state: AgentState) -> IntentLiteral:
    """Sorteia o intent da distribuição calibrada, modulada pela persona.

    - Visita raro (<=1x/semana) → entra mais decidido (compare/purchase 2x).
    - Visita muito (>=5x/semana) → está passeando (browse 1.5x).
    """
    p = state.persona
    weights = dict(_BASE_INTENT_WEIGHTS)
    if p.weekly_visit_frequency <= 1:
        weights["compare"] *= 2.0
        weights["purchase"] *= 2.0
    elif p.weekly_visit_frequency >= 5:
        weights["browse"] *= 1.5

    intents = list(weights.keys())
    return random.choices(intents, weights=[weights[i] for i in intents], k=1)[0]


def _fallback_context(state: AgentState, intent: IntentLiteral) -> DecideSessionContext:
    """Contexto procedural se Qwen falhar — usa atributos da persona.

    Budget realista por intent. Produto stub custa até R$ 3500, então budget
    pequeno sempre dava over_budget e o agente nunca chegava no checkout.
    """
    p = state.persona
    budget = None
    if intent == "purchase":
        budget = round(random.uniform(500, 4000), 2)
    elif intent in ("research", "compare"):
        budget = round(random.uniform(300, 2500), 2)

    return DecideSessionContext(
        target_categories=p.preferred_categories[:2],
        budget_brl=budget,
        purchase_probability=0.65 if intent == "purchase" else 0.25 if intent == "compare" else 0.12,
        reasoning="fallback procedural",
    )


def _render_prompt(state: AgentState, intent: IntentLiteral) -> str:
    p = state.persona
    now = datetime.now(UTC)
    return DECIDE_SESSION.format(
        persona_name=p.name,
        persona_age=p.age,
        persona_occupation=p.occupation,
        income_class=p.income_class.value,
        location_city=p.location_city,
        location_state=p.location_state,
        price_sensitivity=p.price_sensitivity,
        brand_loyalty=p.brand_loyalty,
        risk_tolerance=p.risk_tolerance,
        digital_savviness=p.digital_savviness,
        abandonment_likelihood=p.abandonment_likelihood,
        preferred_categories=", ".join(p.preferred_categories),
        datetime_str=now.strftime("%Y-%m-%d %H:%M"),
        weekday=["seg", "ter", "qua", "qui", "sex", "sáb", "dom"][now.weekday()],
        period_of_day=_period(now.hour),
        session_intent=intent,
    )


def _period(hour: int) -> str:
    if hour < 6:
        return "madrugada"
    if hour < 12:
        return "manhã"
    if hour < 18:
        return "tarde"
    return "noite"


async def run(state: AgentState) -> NodeUpdate:
    """Executa o nó: sorteia intent (procedural), Qwen contextualiza."""
    intent = _sample_intent(state)
    context = await run_qwen_node(
        state=state,
        node_name="decide_session",
        prompt=_render_prompt(state, intent),
        response_model=DecideSessionContext,
        fallback=lambda s: _fallback_context(s, intent),
        max_output_tokens=settings.qwen_decision_max_tokens,
    )
    return {
        **qwen_trace_fields(state),
        "session_intent": SessionIntent(intent),
        "target_categories": context.target_categories,
        "budget_brl": context.budget_brl,
        "purchase_probability": context.purchase_probability,
        "current_page": "decide_session",
    }
