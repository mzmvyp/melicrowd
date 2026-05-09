"""Construção do grafo LangGraph do agente.

O grafo tem 14 nós (4 Qwen + 10 procedurais) e 5 conditional edges.
A entry point é ``load_persona``; a saída é ``END`` (terminação natural
quando a sessão atinge ``abandon`` ou ``write_review``).

**Checkpointer:** padrão é ``MemorySaver`` (in-memory). Em produção
(Fase 5+) usa-se o ``RedisCheckpointer`` (TTL 1h) — pode ser injetado
via parâmetro.
"""
from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

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
from melicrowd.agents.state import AgentState


def build_agent_graph(checkpointer: Any | None = None) -> Any:
    """Constrói o grafo compilado do agente.

    Args:
        checkpointer: instância de ``BaseCheckpointSaver``. Se ``None``,
            usa ``MemorySaver``.

    Returns:
        Grafo compilado pronto para ``ainvoke()``.
    """
    g: StateGraph = StateGraph(AgentState)

    # Nodes
    g.add_node("load_persona", load_persona.run)
    g.add_node("decide_session", decide_session.run)
    g.add_node("auth", auth.run)
    g.add_node("browse_home", browse_home.run)
    g.add_node("search", search.run)
    g.add_node("product_list", product_list.run)
    g.add_node("product_detail", product_detail.run)
    g.add_node("evaluate_item", evaluate_item.run)
    g.add_node("add_to_cart", add_to_cart.run)
    g.add_node("continue_or_checkout", continue_or_checkout.run)
    g.add_node("checkout_decision", checkout_decision.run)
    g.add_node("pay", pay.run)
    g.add_node("abandon", abandon.run)
    g.add_node("write_review", write_review.run)

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

    return g.compile(checkpointer=checkpointer or MemorySaver())
