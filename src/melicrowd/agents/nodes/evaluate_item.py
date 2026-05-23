"""Nó Qwen #2: ``evaluate_item`` — decide adicionar/voltar/sair."""
from __future__ import annotations

import random
from typing import Literal

from pydantic import BaseModel, Field

from melicrowd.agents.prompts import EVALUATE_ITEM
from melicrowd.agents.qwen_runner import run_qwen_node
from melicrowd.agents.state import AgentState, NodeUpdate
from melicrowd.config import settings


class EvaluateItemResponse(BaseModel):
    decision: Literal["add_to_cart", "back_to_list", "exit"]
    reasoning: str = ""
    interest_level: float = Field(ge=0.0, le=1.0, default=0.5)


def _fallback(state: AgentState) -> EvaluateItemResponse:
    """Decisão procedural modulada por persona + intent + budget.

    Calibração de probabilidades pra produzir taxas realistas de e-commerce:
    - intent=purchase: ~40% add_to_cart por produto visto
    - intent=compare:  ~25% add_to_cart
    - intent=research: ~15% add_to_cart
    - intent=browse:   ~5% add_to_cart
    Sem isso, todos os agentes loopam product_list → product_detail → back
    e abandonam após 8 ciclos. Conversion fica em 0%.
    """
    p = state.persona
    product = state.current_product
    if product is None:
        # Sem produto carregado, mesmo assim dá uma chance pequena de "add"
        # (cenário: agente clica sem ver detalhe). Mantém o funil vivo.
        if random.random() < 0.05:
            return EvaluateItemResponse(decision="add_to_cart", reasoning="impulse (no product)")
        return EvaluateItemResponse(decision="back_to_list", reasoning="no product loaded")

    # Base por intent — calibrado para conversion final de 3-8 % (benchmark do varejo BR).
    # Cada sessão visita ~2-4 produtos antes de add_to_cart, então essas probs são
    # POR PRODUTO visto, não por sessão.
    intent = state.session_intent.value if state.session_intent else "browse"
    base_prob_add = {
        "purchase": 0.50,   # decidido a comprar — primeira boa oferta entra no cart
        "compare": 0.30,
        "research": 0.22,
        "browse": 0.15,     # browse ainda tem impulso (15%)
    }.get(intent, 0.20)

    # Modulação por persona
    if p.price_sensitivity > 0.7 and product.price > (state.budget_brl or 99999) * 0.7:
        base_prob_add *= 0.4  # produto caro p/ persona sensível a preço
    if product.rating < 3.5:
        base_prob_add *= 0.5  # rating ruim derruba interesse
    if product.rating > 4.5 and product.review_count > 500:
        base_prob_add *= 1.4  # social proof forte

    # Exit explícito (sair da sessão) é raro — só quando produto MUITO ruim
    # e persona impaciente.
    if product.rating < 3.0 and p.abandonment_likelihood > 0.7 and random.random() < 0.3:
        return EvaluateItemResponse(decision="exit", reasoning="bad rating + impatient")

    decision: Literal["add_to_cart", "back_to_list", "exit"] = (
        "add_to_cart" if random.random() < base_prob_add else "back_to_list"
    )
    return EvaluateItemResponse(
        decision=decision,
        reasoning=f"procedural intent={intent} prob={base_prob_add:.2f}",
        interest_level=min(1.0, base_prob_add * 2),
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
    """Executa o nó.

    Modo default: usa fallback procedural (modulado por persona) sem Qwen
    — o gargalo é Qwen no eval_item porque é chamado 3-8x/sessão. Ative
    Qwen aqui via ``MELICROWD_QWEN_EVALUATE_ITEM_ENABLED=true`` se quiser
    o realismo extra do LLM avaliando produto-a-produto.
    """
    if state.current_product is None:
        return {"current_page": "evaluate_item", "last_evaluation": "back_to_list"}

    if settings.qwen_evaluate_item_enabled:
        response = await run_qwen_node(
            state=state,
            node_name="evaluate_item",
            prompt=_render_prompt(state),
            response_model=EvaluateItemResponse,
            fallback=_fallback,
        )
    else:
        response = _fallback(state)

    return {"current_page": "evaluate_item", "last_evaluation": response.decision}
