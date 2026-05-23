"""Action: ``audit_inventory`` — vendedor consulta catálogo atual da loja."""
from __future__ import annotations

from loguru import logger

from melicrowd.execution.melisim_client import get_client
from melicrowd.sellers.models import SellerProduct
from melicrowd.sellers.state import SellerSessionState

LOGGER = logger.bind(module="sellers.actions.audit_inventory")


async def run(state: SellerSessionState) -> None:
    """Popula ``state.inventory`` com os produtos do vendedor."""
    if not state.melisim_user_id or not state.auth_token:
        return
    client = get_client()
    try:
        products = await client._filter_by_seller(  # noqa: SLF001  (helper interno é OK aqui)
            state.melisim_user_id, auth_token=state.auth_token
        )
        # Aproximadamente uma chamada por página (max 5).
        state.melisim_calls_count += min(5, max(1, len(products) // 50 + 1))
        state.inventory = [
            SellerProduct(
                product_id=p.product_id,
                title=p.title,
                category=p.category,
                price=p.price,
                stock=p.stock,
            )
            for p in products
        ]
        state.products_audited = len(state.inventory)
        LOGGER.info(
            "inventory audited",
            extra={
                "session_id": str(state.session_id),
                "count": len(state.inventory),
                "low_stock": sum(1 for p in state.inventory if p.stock < 10),
            },
        )
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning(
            "audit_inventory failed",
            extra={"session_id": str(state.session_id), "error": str(exc)[:200]},
        )
        state.errors_encountered.append(f"audit: {type(exc).__name__}")
