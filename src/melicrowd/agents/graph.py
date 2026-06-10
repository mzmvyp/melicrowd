"""Construção do grafo LangGraph do agente.

O grafo tem 14 nós (4 Qwen + 10 procedurais) e 5 conditional edges.
A entry point é ``load_persona``; a saída é ``END`` (terminação natural
quando a sessão atinge ``abandon`` ou ``write_review``).

**Checkpointer:** padrão é ``MemorySaver`` (in-memory). Em produção
(Fase 5+) usa-se o ``RedisCheckpointer`` (TTL 1h) — pode ser injetado
via parâmetro.

**Tracker pre-update (importante):**
Cada nó é envolvido por ``_with_tracking()`` que atualiza o
``LiveAgentTracker`` ANTES de o nó começar a executar. Sem isso, o
``astream(stream_mode="updates")`` só emite atualização DEPOIS que o nó
termina — e nós HTTP/Qwen que demoram 1-6s fazem o agente aparecer
travado no nó anterior na UI. O wrapper resolve fazendo a UI ver o
agente na nova estação no instante em que ele entra.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from loguru import logger

from melicrowd.agents import edges
from melicrowd.agents.nodes import (
    abandon,
    add_to_cart,
    auth,
    browse_home,
    checkout_decision,
    continue_or_checkout,
    decide_session,
    evaluate_item,
    load_persona,
    pay,
    product_detail,
    product_list,
    search,
    write_review,
)
from melicrowd.agents.state import AgentState, NodeUpdate
from melicrowd.observability.live_tracker import get_tracker

LOGGER = logger.bind(module="agents.graph")

NodeFn = Callable[[AgentState], Awaitable[NodeUpdate]]

QWEN_NODES = frozenset({"decide_session", "evaluate_item", "checkout_decision", "write_review"})


def _with_tracking(node_name: str, node_fn: NodeFn) -> NodeFn:
    """Envolve um nó para fazer pre-update **visual** no tracker.

    Sequência:
        1. tracker.upsert_from_state(state, station=node_name)  ← antes (só posição visual)
        2. resultado = await node_fn(state)                      ← trabalho real
        3. ... astream emite update no fim; o runner conta a visita
           (``record_node_enter``) e a duração (``record_node_exit``).

    **Importante:** a contagem de visitas (``record_node_enter``) é feita
    SOMENTE no ``runner.py`` quando o update chega. Antes era feita também
    aqui, o que dobrava ``visits_total`` no tracker e divergia do
    ``node_visits_total`` do Prometheus (contado 1× no runner) por um fator 2.
    """

    async def wrapped(state: AgentState) -> NodeUpdate:
        tracker = get_tracker()
        try:
            await tracker.upsert_from_state(
                state,
                worker_id=getattr(state, "worker_id", None),
                station_override=node_name,
                is_thinking=node_name in QWEN_NODES,
                thinking_progress=0.05 if node_name in QWEN_NODES else 0.0,
            )
        except Exception as exc:  # noqa: BLE001  — tracker é best-effort
            LOGGER.debug(
                "tracker pre-update failed",
                extra={"node": node_name, "error": str(exc)[:120]},
            )
        return await node_fn(state)

    wrapped.__name__ = f"tracked_{node_name}"
    return wrapped


def _build_state_graph() -> StateGraph:
    """Monta o ``StateGraph`` (nós + arestas) sem compilar."""
    g: StateGraph = StateGraph(AgentState)

    # Nodes — todos wrappados pra fazer pre-update no tracker.
    g.add_node("load_persona", _with_tracking("load_persona", load_persona.run))
    g.add_node("decide_session", _with_tracking("decide_session", decide_session.run))
    g.add_node("auth", _with_tracking("auth", auth.run))
    g.add_node("browse_home", _with_tracking("browse_home", browse_home.run))
    g.add_node("search", _with_tracking("search", search.run))
    g.add_node("product_list", _with_tracking("product_list", product_list.run))
    g.add_node("product_detail", _with_tracking("product_detail", product_detail.run))
    g.add_node("evaluate_item", _with_tracking("evaluate_item", evaluate_item.run))
    g.add_node("add_to_cart", _with_tracking("add_to_cart", add_to_cart.run))
    g.add_node("continue_or_checkout", _with_tracking("continue_or_checkout", continue_or_checkout.run))
    g.add_node("checkout_decision", _with_tracking("checkout_decision", checkout_decision.run))
    g.add_node("pay", _with_tracking("pay", pay.run))
    g.add_node("abandon", _with_tracking("abandon", abandon.run))
    g.add_node("write_review", _with_tracking("write_review", write_review.run))

    # Linear edges
    g.set_entry_point("load_persona")
    g.add_edge("load_persona", "decide_session")
    g.add_edge("auth", "browse_home")
    g.add_edge("browse_home", "search")
    g.add_edge("search", "product_list")
    g.add_edge("product_list", "product_detail")
    g.add_edge("product_detail", "evaluate_item")
    g.add_edge("add_to_cart", "continue_or_checkout")
    g.add_edge("write_review", END)
    g.add_edge("abandon", END)

    # Conditional edges
    g.add_conditional_edges(
        "decide_session",
        edges.route_after_decide_session,
        {"auth": "auth", "abandon": "abandon"},
    )
    g.add_conditional_edges(
        "evaluate_item",
        edges.route_after_evaluate_item,
        {"add_to_cart": "add_to_cart", "back_to_list": "product_list", "abandon": "abandon"},
    )
    g.add_conditional_edges(
        "continue_or_checkout",
        edges.route_after_continue_or_checkout,
        {"continue": "search", "checkout": "checkout_decision"},
    )
    g.add_conditional_edges(
        "checkout_decision",
        edges.route_after_checkout_decision,
        {"pay": "pay", "abandon": "abandon"},
    )
    g.add_conditional_edges(
        "pay",
        edges.route_after_pay,
        {"write_review": "write_review", "end": END},
    )

    return g


def build_agent_graph(checkpointer: Any | None = None) -> Any:
    """Constrói o grafo compilado do agente.

    Args:
        checkpointer: instância de ``BaseCheckpointSaver``. Se ``None``,
            usa ``MemorySaver``.

    Returns:
        Grafo compilado pronto para ``ainvoke()``.
    """
    return _build_state_graph().compile(checkpointer=checkpointer or MemorySaver())


_default_graph: Any | None = None


def get_default_graph() -> Any:
    """Retorna o grafo compilado default (SEM checkpointer), compilado 1× e reusado.

    A compilação do ``StateGraph`` é cara e era refeita a cada sessão no
    ``runner``; um único grafo compilado atende todas as sessões em paralelo.

    **Sem checkpointer, deliberadamente:** um ``MemorySaver`` único compartilhado
    reteria os checkpoints de TODAS as sessões (thread_id = session_id novo a
    cada sessão, nunca evictado) — vazamento de memória sem limite em runs
    longos. Como nada resume sessões no fluxo default, compilamos sem saver.
    Para replay/recovery (ex.: Redis), injete via ``build_agent_graph(checkpointer)``.
    """
    global _default_graph  # noqa: PLW0603
    if _default_graph is None:
        _default_graph = _build_state_graph().compile()
    return _default_graph
