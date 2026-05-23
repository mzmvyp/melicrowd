"""Action: ``suspend`` — remove produto do catálogo via DELETE /products/{id}."""
from __future__ import annotations

from loguru import logger

from melicrowd.execution.melisim_client import get_client
from melicrowd.sellers.state import SellerSessionState

LOGGER = logger.bind(module="sellers.actions.suspend")


async def run(state: SellerSessionState, *, product_id: str) -> bool:
    """Suspende produto. Returns True se sucedeu."""
    if not state.auth_token:
        return False
    client = get_client()
    ok = await client.delete_product(product_id, auth_token=state.auth_token)
    state.melisim_calls_count += 1
    if ok:
        state.products_suspended += 1
        # Remove do inventory local
        state.inventory = [p for p in state.inventory if p.product_id != product_id]
        LOGGER.info(
            "product suspended",
            extra={"session_id": str(state.session_id), "product_id": product_id},
        )
    return ok
