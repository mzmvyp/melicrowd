"""Nó Qwen #2: ``evaluate_item`` — decide adicionar/voltar/sair."""
from __future__ import annotations

import random
from typing import Literal

from pydantic import BaseModel, Field

from melicrowd.agents.prompts import EVALUATE_ITEM
from melicrowd.agents.qwen_runner import run_qwen_node
from melicrowd.agents.state import AgentState, NodeUpdate


class EvaluateItemResponse(BaseModel):
    decision: Literal["add_to_cart", "back_to_list", "exit"]
    reasoning: str = ""
    interest_level: float = Field(ge=0.0, le=1.0, default=0.5)


def _fallback(state: AgentState) -> EvaluateItemResponse:
    """Decisão procedural baseada em persona + budget."""
    p = state.persona
    product = state.current_product
    if product is None:
        return EvaluateItemResponse(decision="back_to_list", reasoning="no product loaded")

    over_budget = state.budget_brl is not None and product.price > state.budget_brl
    low_rating = product.rating < 3.5
    if over_budget or (low_rating and p.price_sensitivity > 0.5):
        decision: Literal["add_to_cart", "back_to_list", "exit"] = (
            "exit" if random.random() < p.abandonment_likelihood else "back_to_list"
        )
    else:
        # Probabilidade de comprar modulada por purchase_probability + interest.
        base = state.purchase_probability or 0.2
        decision = "add_to_cart" if random.random() < base else "back_to_list"

    return EvaluateItemResponse(
        decision=decision,
        reasoning="fallback procedural",
        interest_level=0.5,
    )


def _render_prompt(state: AgentState) -> str:
    p = state.persona
    product = state.current_product
    if product is None:
        return "no product"
    return EVALUATE_ITEM.format(
        persona_name=p.name,
        persona_age=p.age,
        income_class=p.income_class.value,
        persona_occupation=p.occupation,
        price_sensitivity=p.price_sensitivity,
        brand_loyalty=p.brand_loyalty,
        purchase_drivers=", ".join(p.purchase_drivers),
        product_title=product.title,
        product_category=product.category,
        product_price=product.price,
        product_brand=product.brand,
        product_rating=product.rating,
        product_review_count=product.review_count,
        session_intent=state.session_intent.value if state.session_intent else "browse",
        budget_brl=state.budget_brl or 0,
        cart_summary=", ".join(item.title for item in state.cart) or "vazio",
        cart_total=state.cart_total(),
    )


async def run(state: AgentState) -> NodeUpdate:
    """Executa o nó."""
    if state.current_product is None:
        return {"current_page": "evaluate_item", "last_evaluation": "back_to_list"}
    response = await run_qwen_node(
        state=state,
        node_name="evaluate_item",
        prompt=_render_prompt(state),
        response_model=EvaluateItemResponse,
        fallback=_fallback,
    )
    return {"current_page": "evaluate_item", "last_evaluation": response.decision}
