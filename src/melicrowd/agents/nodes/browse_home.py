"""Nó: ``browse_home`` — visualiza a home (sem chamada de produtos)."""
from __future__ import annotations

from melicrowd.agents.state import AgentState, NodeUpdate


async def run(_state: AgentState) -> NodeUpdate:
    """Só atualiza current_page (a chamada real ao Melisim acontece em search)."""
    return {"current_page": "browse_home"}
