"""Nó: ``add_to_cart`` — adiciona o produto atual ao carrinho local."""
from __future__ import annotations

from melicrowd.agents.state import AgentState, CartItem, NodeUpdate


async def run(state: AgentState) -> NodeUpdate:
    """Adiciona ``current_product`` ao ``cart`` (em memória — Melisim não tem cart)."""
    product = state.current_product
    if product is None:
        return {"current_page": "cart"}
    new_item = CartItem(
        product_id=product.product_id,
        title=product.title,
        price=product.price,
        quantity=1,
    )
    return {
        "current_page": "cart",
        "cart": [*state.cart, new_item],
    }
