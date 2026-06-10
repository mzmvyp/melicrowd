"""Nó: ``search`` — gera query e chama /products/search."""
from __future__ import annotations

import random

from melicrowd.agents.state import AgentState, NodeUpdate
from melicrowd.execution.melisim_client import get_client
from melicrowd.execution.timing import typing_delay


async def run(state: AgentState) -> NodeUpdate:
    """Escolhe uma query (das categorias-alvo) e busca no Melisim."""
    query = (
        random.choice(state.target_categories)
        if state.target_categories
        else random.choice(state.persona.preferred_categories)
    )
    # Humano digita a query antes de buscar (velocidade modulada pela persona).
    await typing_delay(query, state.persona)
    client = get_client()
    products = await client.search_products(query, auth_token=state.auth_token)
    return {
        "current_page": "search",
        "search_queries": [*state.search_queries, query],
        "candidate_products": products,
        "melisim_calls_count": state.melisim_calls_count + 1,
    }
