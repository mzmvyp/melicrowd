"""Markov chain modulada por persona para transições micro do agente.

A LangGraph state machine cobre o macro-fluxo (4 decisões Qwen + 10 nós
procedurais). Entre nós, a *escolha* de "qual produto clicar" e similar
segue uma matriz de transição Markov que pondera comportamento humano
realista.

Esta versão expõe utilitários consultáveis pelos nós procedurais e pelas
routing functions. Não substitui a state machine — complementa.

Estados base:
    home → search → product_list → product_detail
                  ↓
                  category_browse → product_list
    product_detail → add_to_cart → checkout → purchase
                                            → abandon
    product_detail → back_to_list
    qualquer estado → exit
"""
from __future__ import annotations

import random
from typing import Final

import numpy as np

from melicrowd.personas.models import Persona

#: Estados da cadeia Markov.
STATES: Final[list[str]] = [
    "home",            # 0
    "search",          # 1
    "product_list",    # 2
    "product_detail",  # 3
    "compare",         # 4
    "back_to_list",    # 5
    "add_to_cart",     # 6
    "checkout",        # 7
    "exit",            # 8
]
N_STATES: Final[int] = len(STATES)

#: Matriz base 9x9. Cada linha soma 1.0. Linhas calibradas com observações
#: empíricas de e-commerce BR (conversion ~3%, abandono ~70%).
BASE_MATRIX: Final[np.ndarray] = np.array(
    [
        # home  search list  detail comp  back  cart  ckout exit
        [0.00, 0.45, 0.35, 0.00, 0.00, 0.00, 0.00, 0.00, 0.20],  # home
        [0.00, 0.00, 0.85, 0.00, 0.00, 0.00, 0.00, 0.00, 0.15],  # search
        [0.05, 0.10, 0.00, 0.65, 0.00, 0.00, 0.00, 0.00, 0.20],  # list
        [0.00, 0.05, 0.10, 0.00, 0.10, 0.45, 0.20, 0.00, 0.10],  # detail
        [0.00, 0.05, 0.20, 0.55, 0.00, 0.10, 0.05, 0.00, 0.05],  # compare
        [0.05, 0.15, 0.55, 0.10, 0.00, 0.00, 0.00, 0.00, 0.15],  # back
        [0.00, 0.05, 0.10, 0.05, 0.00, 0.00, 0.00, 0.65, 0.15],  # cart
        [0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.05, 0.00, 0.95],  # checkout (transitional)
        [0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 1.00],  # exit
    ],
    dtype=np.float64,
)


def _index_of(state: str) -> int:
    return STATES.index(state)


def get_persona_matrix(persona: Persona) -> np.ndarray:
    """Retorna matriz de transição modulada pela persona.

    Modulações aplicadas:
    - ``price_sensitivity`` alta → mais transições para ``compare`` e ``back_to_list``.
    - ``digital_savviness`` baixa → menos transições diretas para ``search`` (vai mais por categorias / scroll).
    - ``abandonment_likelihood`` alta → mais transições para ``exit`` em qualquer estado.
    - ``brand_loyalty`` alta → menos transições para ``compare``.

    Args:
        persona: persona a usar para modular.

    Returns:
        Matriz numpy 9x9 normalizada (linhas somam 1.0).
    """
    matrix = BASE_MATRIX.copy()

    # 1. price_sensitivity → mais comparação (compare) e voltas (back_to_list).
    if persona.price_sensitivity > 0.6:
        boost = (persona.price_sensitivity - 0.5) * 0.2
        matrix[_index_of("product_detail"), _index_of("compare")] += boost
        matrix[_index_of("product_detail"), _index_of("back_to_list")] += boost
        matrix[_index_of("product_detail"), _index_of("add_to_cart")] -= boost

    # 2. digital_savviness baixa → menos search direto, mais browsing.
    if persona.digital_savviness < 0.4:
        delta = (0.5 - persona.digital_savviness) * 0.15
        matrix[_index_of("home"), _index_of("search")] -= delta
        matrix[_index_of("home"), _index_of("product_list")] += delta

    # 3. abandonment_likelihood → mais exits.
    if persona.abandonment_likelihood > 0.5:
        boost = (persona.abandonment_likelihood - 0.5) * 0.15
        for s in ("product_detail", "product_list", "search"):
            matrix[_index_of(s), _index_of("exit")] += boost
            # subtrai proporcionalmente das outras
            row = matrix[_index_of(s)]
            non_exit_mask = np.arange(N_STATES) != _index_of("exit")
            row[non_exit_mask] -= boost / non_exit_mask.sum()

    # 4. brand_loyalty alta → menos compare.
    if persona.brand_loyalty > 0.6:
        cut = (persona.brand_loyalty - 0.5) * 0.1
        matrix[_index_of("product_detail"), _index_of("compare")] -= cut
        matrix[_index_of("product_detail"), _index_of("add_to_cart")] += cut

    # Garante valores não-negativos antes da normalização.
    matrix = np.maximum(matrix, 0.0)

    # Normaliza cada linha.
    row_sums = matrix.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1.0
    return matrix / row_sums


def next_state(current: str, persona: Persona) -> str:
    """Sorteia o próximo estado dado o atual e a persona.

    Args:
        current: nome do estado atual.
        persona: persona alocada à sessão.

    Returns:
        Nome do próximo estado.
    """
    matrix = get_persona_matrix(persona)
    idx = _index_of(current)
    probs = matrix[idx]
    choice = random.choices(STATES, weights=probs.tolist(), k=1)[0]
    return choice
