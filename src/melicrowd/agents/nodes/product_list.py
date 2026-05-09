"""Nó: ``product_list`` — escaneia a lista de resultados."""
from __future__ import annotations

from melicrowd.agents.state import AgentState, NodeUpdate


async def run(state: AgentState) -> NodeUpdate:
    """Marca current_page e devolve."""
    return {"current_page": "product_list"}
