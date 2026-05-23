"""Action: ``update_price`` — ajusta preço de um produto via PUT /products/{id}."""
from __future__ import annotations

import random

import httpx
from loguru import logger

from melicrowd.execution.melisim_client import get_client
from melicrowd.sellers.models import PriceStrategy
from melicrowd.sellers.state import SellerSessionState

LOGGER = logger.bind(module="sellers.actions.update_price")


def _new_price(current: float, strategy: PriceStrategy) -> float:
    """Calcula novo preço modulado pela estratégia.

    aggressive: -10% a -20% (corte)
    premium:    +5% a +15% (sobe)
    standard:   ±10%
    """
    if strategy == PriceStrategy.AGGRESSIVE:
        delta_pct = -random.uniform(0.05, 0.20)
    elif strategy == PriceStrategy.PREMIUM:
        delta_pct = random.uniform(0.05, 0.15)
    else:
        delta_pct = random.uniform(-0.10, 0.10)
    new = current * (1 + delta_pct)
    return round(max(1.0, new), 2)


async def run(state: SellerSessionState, *, product_id: str) -> bool:
    """Ajusta preço do produto. Returns True se sucedeu."""
    if not state.auth_token:
        return False
    # Encontra o produto no inventory pra saber o preço atual.
    current = next((p for p in state.inventory if p.product_id == product_id), None)
    if current is None:
        return False
    new_price = _new_price(current.price, state.seller_persona.price_strategy)
    if abs(new_price - current.price) < 0.5:
        return False  # não vale chamar HTTP por mudança ínfima
    client = get_client()
    try:
        updated = await client.update_product(
            product_id, price=new_price, auth_token=state.auth_token
        )
        state.melisim_calls_count += 1
        state.prices_updated += 1
        LOGGER.info(
            "price updated",
            extra={
                "session_id": str(state.session_id),
                "product_id": product_id,
                "old_price": current.price,
                "new_price": updated.price,
            },
        )
        return True
    except httpx.HTTPStatusError as exc:
        LOGGER.debug(
            "update_price failed",
            extra={"product_id": product_id, "status": exc.response.status_code},
        )
        return False
    except Exception as exc:  # noqa: BLE001
        state.errors_encountered.append(f"update_price: {type(exc).__name__}")
        return False
