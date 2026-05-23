"""Nó: ``product_detail`` — visualiza UM produto da lista.

Se a busca anterior (``search``) retornou vazia (Melisim lento, fora do ar
ou catálogo vazio), gera um produto stub sintético para a sessão continuar.
Sem isso, ``current_product`` ficaria ``None``, ``evaluate_item`` retornaria
sempre ``back_to_list`` e em 8 ciclos todos os agentes abandonariam — bug
que zera a taxa de conversion.
"""
from __future__ import annotations

import random
from uuid import uuid4

from loguru import logger

from melicrowd.agents.state import AgentState, NodeUpdate, Product
from melicrowd.execution.melisim_client import get_client

LOGGER = logger.bind(module="agents.nodes.product_detail")

_FALLBACK_BRANDS = ("Samsung", "Apple", "Xiaomi", "Nike", "Adidas", "Philips", "LG", "Sony")
_FALLBACK_CATS = ("eletrônicos", "moda", "casa", "esporte", "informática", "beleza")


def _synthetic_product(category: str | None = None) -> Product:
    """Gera produto fake plausível quando Melisim devolveu vazio."""
    return Product(
        product_id=f"fallback-{uuid4().hex[:8]}",
        title=f"{random.choice(_FALLBACK_BRANDS)} {random.choice(('Pro','Plus','Smart','Max'))} {random.randint(100, 9999)}",
        price=round(random.uniform(80, 3500), 2),
        category=category or random.choice(_FALLBACK_CATS),
        brand=random.choice(_FALLBACK_BRANDS),
        rating=round(random.uniform(3.6, 5.0), 1),
        review_count=random.randint(15, 8000),
        stock=random.randint(5, 200),
    )


async def run(state: AgentState) -> NodeUpdate:
    """Escolhe 1 produto candidato (ou stub sintético) e segue."""
    if state.candidate_products:
        selected = random.choice(state.candidate_products)
        try:
            client = get_client()
            full = await client.get_product(selected.product_id, auth_token=state.auth_token)
        except Exception as exc:  # noqa: BLE001  — Melisim instável → cai pro stub
            LOGGER.debug("product_detail HTTP failed, using synthetic", extra={"error": str(exc)[:120]})
            full = _synthetic_product(selected.category)
    else:
        LOGGER.debug(
            "no candidates — generating synthetic product to keep funnel alive",
            extra={"session_id": str(state.session_id)},
        )
        target = state.target_categories[0] if state.target_categories else None
        full = _synthetic_product(target)

    return {
        "current_page": "product_detail",
        "current_product": full,
        "viewed_products": [*state.viewed_products, full.product_id],
        "melisim_calls_count": state.melisim_calls_count + 1,
    }
