"""Nó: ``auth`` — signup ou login no Melisim.

Estratégia (decisão #4 do RECON):
- Se intent é ``browse`` ou ``research``: navega anônimo (sem auth). Skip.
- Se intent é ``compare`` ou ``purchase``: cria/loga usuário BUYER.
- A rotação de identidade (criar novo user a cada N sessões) é feita pelo
  orchestrator (Fase 5), não aqui.
"""
from __future__ import annotations

import random

from loguru import logger

from melicrowd.agents.state import AgentState, NodeUpdate, SessionIntent
from melicrowd.execution.melisim_client import get_client

LOGGER = logger.bind(module="agents.nodes.auth")


async def run(state: AgentState) -> NodeUpdate:
    """Faz signup; só aciona quando intent exige autenticação."""
    if state.session_intent in (SessionIntent.BROWSE, SessionIntent.RESEARCH):
        LOGGER.debug("skipping auth (anonymous browse)", extra={"session_id": str(state.session_id)})
        return {"current_page": "auth"}

    client = get_client()
    p = state.persona
    suffix = random.randint(10000, 99999)
    email = f"{p.name.lower().replace(' ', '.')}+{suffix}@melicrowd.test"
    result = await client.signup(name=p.name, email=email, password="melicrowd-test-pw")
    LOGGER.info(
        "auth ok",
        extra={"session_id": str(state.session_id), "user_id": result.user_id},
    )
    # melisim_calls_count vai no UPDATE retornado (não em mutação in-place):
    # LangGraph só propaga o que o nó retorna — incremento in-place se perdia.
    return {
        "melisim_user_id": result.user_id,
        "auth_token": result.access_token,
        "melisim_calls_count": state.melisim_calls_count + 1,
        "current_page": "auth",
    }
