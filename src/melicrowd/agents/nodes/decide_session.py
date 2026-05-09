"""Nó Qwen #1: ``decide_session`` — define intent + categorias + budget."""
from __future__ import annotations

import random
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from melicrowd.agents.prompts import DECIDE_SESSION
from melicrowd.agents.qwen_runner import run_qwen_node
from melicrowd.agents.state import AgentState, NodeUpdate, SessionIntent


class DecideSessionResponse(BaseModel):
    """Resposta esperada do Qwen para decide_session."""

    session_intent: Literal["browse", "research", "compare", "purchase"]
    target_categories: list[str] = Field(default_factory=list)
    budget_brl: float | None = None
    purchase_probability: float = Field(ge=0.0, le=1.0, default=0.3)
    reasoning: str = ""


def _fallback(state: AgentState) -> DecideSessionResponse:
    """Decisão procedural se Qwen falhar — usa atributos da persona."""
    p = state.persona
    # Persona com weekly_visit_frequency alta → tende a "browse".
    if p.weekly_visit_frequency >= 5:
        intent: Literal["browse", "research", "compare", "purchase"] = "browse"
    elif p.weekly_visit_frequency <= 1:
        intent = "purchase"
    else:
        intent = random.choice(["research", "compare"])

    return DecideSessionResponse(
        session_intent=intent,
        target_categories=p.preferred_categories[:2],
        budget_brl=None if intent == "browse" else round(random.uniform(100, 1500), 2),
        purchase_probability=0.5 if intent == "purchase" else 0.15,
        reasoning="fallback procedural",
    )


def _render_prompt(state: AgentState) -> str:
    p = state.persona
    now = datetime.utcnow()
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
    """Executa o nó: chama Qwen, atualiza state."""
    response = await run_qwen_node(
        state=state,
        node_name="decide_session",
        prompt=_render_prompt(state),
        response_model=DecideSessionResponse,
        fallback=_fallback,
    )
    return {
        "session_intent": SessionIntent(response.session_intent),
        "target_categories": response.target_categories,
        "budget_brl": response.budget_brl,
        "purchase_probability": response.purchase_probability,
    }
