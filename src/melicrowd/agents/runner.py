"""Runner — interface high-level para executar 1 sessão completa.

Usado por:
- ``melicrowd.agents.demo`` (CLI de teste manual)
- ``melicrowd.orchestrator.pool`` (Fase 5)
"""
from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from loguru import logger

from melicrowd.agents.graph import build_agent_graph
from melicrowd.agents.state import AgentState
from melicrowd.personas.models import Persona

LOGGER = logger.bind(module="agents.runner")


async def run_session(
    persona: Persona,
    *,
    session_id: UUID | None = None,
    checkpointer: Any | None = None,
) -> AgentState:
    """Roda 1 sessão completa para a ``persona`` informada.

    Args:
        persona: persona alocada para esta sessão.
        session_id: UUID da sessão. Default: novo UUID4.
        checkpointer: ``BaseCheckpointSaver``. Default: ``MemorySaver``.

    Returns:
        ``AgentState`` final (com outcome e métricas preenchidos).
    """
    sid = session_id or uuid4()
    initial = AgentState(session_id=sid, persona=persona)
    graph = build_agent_graph(checkpointer)
    config = {"configurable": {"thread_id": str(sid)}, "recursion_limit": 100}

    LOGGER.debug("session start", extra={"session_id": str(sid), "persona_id": str(persona.persona_id)})
    final_state = await graph.ainvoke(initial.model_dump(), config=config)
    LOGGER.info(
        "session end",
        extra={
            "session_id": str(sid),
            "outcome": final_state.get("outcome", "unknown"),
            "qwen_calls": final_state.get("qwen_calls_count", 0),
            "melisim_calls": final_state.get("melisim_calls_count", 0),
        },
    )

    if isinstance(final_state, AgentState):
        return final_state
    return AgentState.model_validate(final_state)
