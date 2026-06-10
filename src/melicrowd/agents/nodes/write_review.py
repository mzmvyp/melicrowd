"""Nó Qwen #4: ``write_review`` — gera review pós-compra (opcional, ~30%).

NOTE: Melisim não tem endpoint /reviews. Review fica só no Kafka como
``events.simulator.decision_made`` (publicação real entra na Fase 4).
"""
from __future__ import annotations

import random
from typing import Literal

from pydantic import BaseModel, Field

from melicrowd.agents.prompts import WRITE_REVIEW
from melicrowd.agents.qwen_runner import qwen_trace_fields, run_qwen_node
from melicrowd.agents.state import AgentState, NodeUpdate


class WriteReviewResponse(BaseModel):
    rating: int = Field(ge=1, le=5)
    title: str = ""
    body: str = ""
    tone: Literal["positive", "neutral", "negative"] = "positive"


def _fallback(state: AgentState) -> WriteReviewResponse:
    """Review canned se Qwen falhar."""
    return WriteReviewResponse(
        rating=random.randint(3, 5),
        title="Bom produto",
        body=f"Comprei e gostei. Persona {state.persona.name} aprova.",
        tone="positive",
    )


def _render_prompt(state: AgentState) -> str:
    p = state.persona
    if not state.cart:
        return "no purchase"
    item = state.cart[0]
    return WRITE_REVIEW.format(
        persona_name=p.name,
        persona_age=p.age,
        persona_occupation=p.occupation,
        income_class=p.income_class.value,
        product_title=item.title,
        product_price=item.price,
        interest_level=0.7,
    )


async def run(state: AgentState) -> NodeUpdate:
    """Roda o nó (caller decide se chama via persona.review_likelihood)."""
    await run_qwen_node(
        state=state,
        node_name="write_review",
        prompt=_render_prompt(state),
        response_model=WriteReviewResponse,
        fallback=_fallback,
    )
    return {**qwen_trace_fields(state), "current_page": "write_review"}
