"""Nó: ``browse_home`` — carrega a home (vitrine) do Melisim.

Exercita ``GET /api/v1/products`` — a rota de listagem que antes nenhum buyer
cobria (a descoberta era 100% via search). A vitrine alimenta
``candidate_products`` como ponto de partida; o ``search`` seguinte sobrescreve
com resultados da busca, então isso não distorce o funil — só garante
cobertura da rota e dá conteúdo à home.

Falha/vazio é tolerado: a home não pode derrubar a sessão (best-effort).
"""
from __future__ import annotations

from loguru import logger

from melicrowd.agents.state import AgentState, NodeUpdate
from melicrowd.execution.melisim_client import get_client
from melicrowd.execution.timing import page_load_delay, think_time

LOGGER = logger.bind(module="agents.nodes.browse_home")


async def run(state: AgentState) -> NodeUpdate:
    """Carrega a vitrine da home (1 página pequena) e pausa como humano."""
    await page_load_delay()

    update: NodeUpdate = {"current_page": "browse_home"}
    try:
        client = get_client()
        showcase = await client.list_products(page=1, size=8, auth_token=state.auth_token)
        update["melisim_calls_count"] = state.melisim_calls_count + 1
        if showcase:
            update["candidate_products"] = showcase
    except Exception as exc:  # noqa: BLE001 — home é best-effort
        LOGGER.debug("home showcase failed", extra={"error": str(exc)[:120]})

    # Olhando a vitrine antes de partir pra busca.
    await think_time(state.persona)
    return update
