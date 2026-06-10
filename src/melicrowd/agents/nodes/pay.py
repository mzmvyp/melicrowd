"""Nó: ``pay`` — cria pedido + paga via Melisim."""
from __future__ import annotations

import random
from uuid import uuid4

import httpx
from loguru import logger

from melicrowd.agents.state import AgentState, NodeUpdate, SessionOutcome
from melicrowd.execution.melisim_client import MelisimClient, get_client

LOGGER = logger.bind(module="agents.nodes.pay")


async def _ensure_auth(state: AgentState, client: MelisimClient) -> bool:
    """Lazy auth no checkout: visitante anônimo (intent browse/research) que
    decidiu comprar autentica AGORA — fluxo real de e-commerce (guest → login
    no checkout). Sessões compare/purchase já vêm autenticadas do nó ``auth``.

    Retorna ``True`` se há credencial válida ao fim; ``False`` se o signup falhou.
    """
    if state.melisim_user_id and state.auth_token:
        return True
    p = state.persona
    suffix = random.randint(10000, 99999)
    email = f"{p.name.lower().replace(' ', '.')}+{suffix}@melicrowd.test"
    try:
        result = await client.signup(name=p.name, email=email, password="melicrowd-test-pw")
    except Exception as exc:  # noqa: BLE001 — signup best-effort; falha → abandona
        LOGGER.warning("lazy auth at checkout failed", extra={"error": str(exc)[:120]})
        return False
    state.melisim_user_id = result.user_id
    state.auth_token = result.access_token
    state.melisim_calls_count += 1
    LOGGER.info("lazy auth ok at checkout", extra={"session_id": str(state.session_id)})
    return True


async def run(state: AgentState) -> NodeUpdate:
    """Cria orders no Melisim (1 por item do carrinho) e paga cada um.

    Telemetria de validação: separa **compra confirmada** (order aceita E
    pagamento ok no gateway, verificado via ``GET /orders/{{id}}``) de
    **intenção de compra** (item sintético ``fallback-*`` ou order rejeitada
    com 4xx). ``purchase_total_brl`` soma ambos (funil/AOV interno);
    ``confirmed_total_brl``/``orders_confirmed`` batem com o banco do MeliSim.
    """
    client = get_client()
    if not await _ensure_auth(state, client):
        LOGGER.warning("pay sem auth e signup falhou — abandona")
        return {"outcome": SessionOutcome.ABANDONED_CART, "current_page": "pay"}
    total_paid = 0.0
    confirmed_total = 0.0
    orders_confirmed = 0
    orders_rejected = 0
    melisim_calls = state.melisim_calls_count

    for item in state.cart:
        if item.product_id.startswith("fallback-"):
            # Produto synthetic — Melisim retornaria 400. Conta como intenção
            # de compra no funil (não como order confirmada).
            total_paid += item.price * item.quantity
            orders_rejected += 1
            LOGGER.debug(
                "skipping melisim order for synthetic product",
                extra={"product_id": item.product_id, "price": item.price},
            )
            continue
        try:
            order = await client.create_order(
                buyer_id=state.melisim_user_id,
                product_id=item.product_id,
                quantity=item.quantity,
                auth_token=state.auth_token,
            )
            melisim_calls += 1
        except httpx.HTTPStatusError as exc:
            # Melisim rejeitou (produto não existe, estoque, etc) — agente
            # tentou genuinamente comprar. Conta como intenção, não confirmada.
            LOGGER.debug(
                "create_order rejected by melisim — counting as intent",
                extra={"product_id": item.product_id, "status": exc.response.status_code},
            )
            total_paid += item.price * item.quantity
            orders_rejected += 1
            continue
        try:
            ok = await client.pay_order(
                order_id=order.order_id,
                amount=order.total_amount,
                method="pix",
                idempotency_key=str(uuid4()),
                auth_token=state.auth_token,
            )
            melisim_calls += 1
        except httpx.HTTPStatusError as exc:
            LOGGER.debug(
                "pay rejected — order created but payment failed",
                extra={"order_id": order.order_id, "status": exc.response.status_code},
            )
            ok = False
        if not ok:
            orders_rejected += 1
            continue

        total_paid += order.total_amount
        # Validação ponta-a-ponta: confere no gateway se a order de fato
        # transicionou após o pagamento (exercita GET /orders/{id} — rota que
        # nenhum buyer cobria). Falha na consulta não derruba a compra.
        order_status = "UNKNOWN"
        try:
            order_status = await client.get_order_status(
                order.order_id, auth_token=state.auth_token
            )
            melisim_calls += 1
        except Exception as exc:  # noqa: BLE001 — verificação best-effort
            LOGGER.debug(
                "order status check failed",
                extra={"order_id": order.order_id, "error": str(exc)[:120]},
            )
        if order_status in ("CANCELLED", "FAILED"):
            LOGGER.warning(
                "payment accepted but order not confirmed by melisim",
                extra={"order_id": order.order_id, "status": order_status},
            )
            orders_rejected += 1
        else:
            orders_confirmed += 1
            confirmed_total += order.total_amount

    LOGGER.info(
        "pay completed",
        extra={
            "session_id": str(state.session_id),
            "items_paid": len(state.cart),
            "total_brl": total_paid,
            "orders_confirmed": orders_confirmed,
            "orders_rejected": orders_rejected,
        },
    )
    return {
        "outcome": SessionOutcome.PURCHASED,
        "purchase_total_brl": round(total_paid, 2),
        "confirmed_total_brl": round(confirmed_total, 2),
        "orders_confirmed": orders_confirmed,
        "orders_rejected": orders_rejected,
        "current_page": "pay",
        "melisim_calls_count": melisim_calls,
        "melisim_user_id": state.melisim_user_id,
        "auth_token": state.auth_token,
    }
