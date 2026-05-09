"""Nó: ``continue_or_checkout`` — decide continuar comprando ou ir pra checkout."""
from __future__ import annotations

import random

from melicrowd.agents.state import AgentState, NodeUpdate

#: Probabilidade base de continuar comprando após adicionar 1 item.
BASE_CONTINUE_PROB = 0.4


async def run(state: AgentState) -> NodeUpdate:
    """Decisão procedural: combina cart_size, budget e persona."""
    cart_size = len(state.cart)
    base_continue = max(0.05, BASE_CONTINUE_PROB - 0.15 * cart_size)
    budget_consumed = (
        state.cart_total() / state.budget_brl
        if state.budget_brl and state.budget_brl > 0
        else 0.5
    )
    if budget_consumed > 0.7:
        base_continue *= 0.3  # quase sempre vai pra checkout

    next_step = "continue" if random.random() < base_continue else "checkout"
    return {"current_page": next_step, "last_continue_decision": next_step}
