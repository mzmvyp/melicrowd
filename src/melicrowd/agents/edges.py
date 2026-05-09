"""Routing functions (conditional edges) do grafo LangGraph.

Cada função recebe ``AgentState`` e retorna uma string que LangGraph mapeia
para o próximo nó. Mapeamento explícito está em ``graph.py``.
"""
from __future__ import annotations

import random

from melicrowd.agents.state import AgentState, SessionIntent


def route_after_decide_session(state: AgentState) -> str:
    """``decide_session`` → ``auth`` (todos casos seguem pra auth, que decide skip)."""
    if state.session_intent is None:
        return "abandon"
    return "auth"


def route_after_evaluate_item(state: AgentState) -> str:
    """Rota baseada na decisão Qwen do evaluate_item."""
    decision = state.last_evaluation or "back_to_list"
    if decision == "add_to_cart":
        return "add_to_cart"
    if decision == "exit":
        return "abandon"
    # Sem resultados de busca — voltar à lista só repete o mesmo estado vazio.
    if not state.candidate_products:
        return "abandon"
    # back_to_list — limita re-loops para evitar sessões infinitas.
    if len(state.viewed_products) >= 8:
        return "abandon"
    return "back_to_list"


def route_after_continue_or_checkout(state: AgentState) -> str:
    """Rota baseada na decisão procedural de continuar comprando."""
    return state.last_continue_decision or "checkout"


def route_after_checkout_decision(state: AgentState) -> str:
    """Rota baseada na decisão Qwen do checkout."""
    return "pay" if state.last_checkout_decision == "pay" else "abandon"


def route_after_pay(state: AgentState) -> str:
    """Pós-compra: 30% chance de escrever review (modulado por persona)."""
    threshold = state.persona.review_likelihood
    return "write_review" if random.random() < threshold else "end"
