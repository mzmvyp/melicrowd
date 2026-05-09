"""Nó: ``product_detail`` — visualiza UM produto da lista."""
from __future__ import annotations

import random

from loguru import logger

from melicrowd.agents.state import AgentState, NodeUpdate
from melicrowd.execution.melisim_client import get_client

LOGGER = logger.bind(module="agents.nodes.product_detail")


async def run(state: AgentState) -> NodeUpdate:
    """Escolhe 1 produto candidato, faz GET de detalhe, atualiza state."""
    if not state.candidate_products:
        LOGGER.warning("no candidates — falling back to empty detail", extra={"session_id": str(state.session_id)})
        return {"current_page": "product_detail"}

    selected = random.choice(state.candidate_products)
    client = get_client()
    full = await client.get_product(selected.product_id, auth_token=state.auth_token)
    return {
        "current_page": "product_detail",
        "current_product": full,
        "viewed_products": [*state.viewed_products, full.product_id],
        "melisim_calls_count": state.melisim_calls_count + 1,
    }
