"""Nó: ``abandon`` — termina a sessão sem comprar."""
from __future__ import annotations

from melicrowd.agents.state import AgentState, NodeUpdate, SessionOutcome


async def run(state: AgentState) -> NodeUpdate:
    """Define outcome em ``abandoned_cart`` ou ``browsed_only`` conforme houver cart."""
    outcome = SessionOutcome.ABANDONED_CART if state.cart else SessionOutcome.BROWSED_ONLY
    if not state.viewed_products:
        outcome = SessionOutcome.BOUNCED
    return {"outcome": outcome, "current_page": "end"}
