"""Nó: ``pay`` — cria pedido + paga via Melisim."""
from __future__ import annotations

from uuid import uuid4

from loguru import logger

from melicrowd.agents.state import AgentState, NodeUpdate, SessionOutcome
from melicrowd.execution.melisim_client import get_client

LOGGER = logger.bind(module="agents.nodes.pay")


async def run(state: AgentState) -> NodeUpdate:
    """Cria orders no Melisim (1 por item do carrinho) e paga cada um."""
    if not state.melisim_user_id or not state.auth_token:
        LOGGER.warning("pay called without auth — falling back to abandon")
        return {"outcome": SessionOutcome.ABANDONED_CART, "current_page": "end"}

    client = get_client()
    total_paid = 0.0
    melisim_calls = state.melisim_calls_count

    for item in state.cart:
        order = await client.create_order(
            buyer_id=state.melisim_user_id,
            product_id=item.product_id,
            quantity=item.quantity,
            auth_token=state.auth_token,
        )
        melisim_calls += 1
        ok = await client.pay_order(
            order_id=order.order_id,
            amount=order.total_amount,
            method="pix",
            idempotency_key=str(uuid4()),
            auth_token=state.auth_token,
        )
        melisim_calls += 1
        if ok:
            total_paid += order.total_amount

    LOGGER.info(
        "pay completed",
        extra={
            "session_id": str(state.session_id),
            "items_paid": len(state.cart),
            "total_brl": total_paid,
        },
    )
    return {
        "outcome": SessionOutcome.PURCHASED,
        "purchase_total_brl": round(total_paid, 2),
        "current_page": "paid",
        "melisim_calls_count": melisim_calls,
    }
