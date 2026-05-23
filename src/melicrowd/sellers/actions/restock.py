"""Action: ``restock`` — incrementa estoque de produto via PATCH /products/{id}/stock."""
from __future__ import annotations

import httpx
from loguru import logger

from melicrowd.execution.melisim_client import get_client
from melicrowd.sellers.state import SellerSessionState

LOGGER = logger.bind(module="sellers.actions.restock")


async def run(state: SellerSessionState, *, product_id: str, delta: int) -> bool:
    """Aumenta estoque de ``product_id`` em ``delta`` unidades.

    Returns:
        True se sucedeu.
    """
    if not state.auth_token or delta <= 0:
        return False
    client = get_client()
    try:
        updated = await client.update_stock(product_id, delta=delta, auth_token=state.auth_token)
        state.melisim_calls_count += 1
        state.products_restocked += 1
        LOGGER.info(
            "restock ok",
            extra={
                "session_id": str(state.session_id),
                "product_id": product_id,
                "delta": delta,
                "new_stock": updated.stock,
            },
        )
        return True
    except httpx.HTTPStatusError as exc:
        LOGGER.debug(
            "restock failed (HTTP)",
            extra={"product_id": product_id, "status": exc.response.status_code},
        )
        return False
    except Exception as exc:  # noqa: BLE001
        state.errors_encountered.append(f"restock: {type(exc).__name__}")
        return False
