"""Nó: ``load_persona`` — bootstrap da sessão.

A persona já vem injetada na ``AgentState`` pelo ``runner`` (não há lookup aqui).
Este nó apenas registra o início e marca timestamp.
"""
from __future__ import annotations

from datetime import datetime, timezone

from loguru import logger

from melicrowd.agents.state import AgentState, NodeUpdate

LOGGER = logger.bind(module="agents.nodes.load_persona")


async def run(state: AgentState) -> NodeUpdate:
    """Marca o início da sessão e loga a persona alocada."""
    LOGGER.info(
        "session started",
        extra={
            "session_id": str(state.session_id),
            "persona_id": str(state.persona.persona_id),
            "persona_name": state.persona.name,
            "income_class": state.persona.income_class.value,
        },
    )
    return {
        "current_page": "home",
        "started_at": datetime.now(timezone.utc),
        "last_action_at": datetime.now(timezone.utc),
    }
