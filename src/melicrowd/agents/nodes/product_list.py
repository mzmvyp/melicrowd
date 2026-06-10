"""Nó: ``product_list`` — escaneia a lista de resultados."""
from __future__ import annotations

from melicrowd.agents.state import AgentState, NodeUpdate
from melicrowd.execution.timing import scroll_delay


async def run(state: AgentState) -> NodeUpdate:
    """Humano rola a listagem antes de clicar num produto."""
    await scroll_delay(state.persona)
    return {"current_page": "product_list"}
