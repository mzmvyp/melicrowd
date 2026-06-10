"""Nó: ``add_to_cart`` — adiciona o produto atual ao carrinho local."""
from __future__ import annotations

import random

from melicrowd.agents.state import AgentState, CartItem, NodeUpdate


def _sample_quantity() -> int:
    """Quantidade realista: maioria leva 1; itens repetidos são minoria.

    Sem isso, ``POST /orders`` nunca era exercitado com quantity > 1 — uma
    lacuna de cobertura na validação do MeliSim (estoque/total com múltiplos).
    """
    return random.choices([1, 2, 3], weights=[0.72, 0.20, 0.08], k=1)[0]


async def run(state: AgentState) -> NodeUpdate:
    """Adiciona ``current_product`` ao ``cart`` (em memória — Melisim não tem cart)."""
    product = state.current_product
    if product is None:
        return {"current_page": "add_to_cart"}
    new_item = CartItem(
        product_id=product.product_id,
        title=product.title,
        price=product.price,
        quantity=_sample_quantity(),
    )
    return {
        "current_page": "add_to_cart",
        "cart": [*state.cart, new_item],
    }
