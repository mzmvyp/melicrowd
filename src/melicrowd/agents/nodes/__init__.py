"""Nós da state machine LangGraph.

14 nós no total:
- 4 Qwen (decide_session, evaluate_item, checkout_decision, write_review)
- 10 procedurais (carregam persona, fazem auth, navegam, gerenciam carrinho, terminam sessão)

Cada nó recebe ``AgentState``, retorna ``NodeUpdate`` (dict de campos a atualizar).
"""
from __future__ import annotations

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

__all__ = [
    "abandon",
    "add_to_cart",
    "auth",
    "browse_home",
    "checkout_decision",
    "continue_or_checkout",
    "decide_session",
    "evaluate_item",
    "load_persona",
    "pay",
    "product_detail",
    "product_list",
    "search",
    "write_review",
]
