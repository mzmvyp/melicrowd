"""Action: ``check_notifications`` — lê alertas do stock-monitor e popula state."""
from __future__ import annotations

from typing import Any

from loguru import logger

from melicrowd.execution.melisim_client import get_client
from melicrowd.sellers.models import StockAlert
from melicrowd.sellers.state import SellerSessionState

LOGGER = logger.bind(module="sellers.actions.check_notifications")


async def run(state: SellerSessionState) -> None:
    """Popula ``state.pending_alerts`` com notificações de estoque baixo."""
    if not state.melisim_user_id or not state.auth_token:
        return
    client = get_client()
    try:
        notifs = await client.get_notifications(state.melisim_user_id, auth_token=state.auth_token)
        state.melisim_calls_count += 1
        alerts = [a for a in (_parse_alert(n) for n in notifs) if a is not None]
        state.pending_alerts = alerts
        LOGGER.info(
            "notifications fetched",
            extra={
                "session_id": str(state.session_id),
                "total": len(notifs),
                "stock_alerts": len(alerts),
            },
        )
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning(
            "check_notifications failed",
            extra={"session_id": str(state.session_id), "error": str(exc)[:200]},
        )
        state.errors_encountered.append(f"notifications: {type(exc).__name__}")


def _parse_alert(notif: dict[str, Any]) -> StockAlert | None:
    """Extrai um StockAlert de uma notificação do Melisim.

    Schema varia entre versões; aceita campos comuns.
    """
    event_type = (notif.get("event_type") or notif.get("eventType") or "").lower()
    if "stock" not in event_type and "estoque" not in event_type:
        return None
    payload = notif.get("payload") or notif.get("data") or notif
    if not isinstance(payload, dict):
        return None
    product_id = payload.get("product_id") or payload.get("productId")
    if not product_id:
        return None
    return StockAlert(
        product_id=str(product_id),
        product_title=str(payload.get("title") or payload.get("product_title") or "produto"),
        current_stock=int(payload.get("stock") or 0),
        threshold=int(payload.get("threshold") or 10),
    )
