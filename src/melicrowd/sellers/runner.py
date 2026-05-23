"""Runner — executa 1 sessão de vendedor.

Loop procedural simples (não LangGraph — não há ramificações complexas
suficientes pra justificar). Qwen é usado em 3 pontos: decidir foco da
sessão, avaliar cada notificação de estoque, e gerar texto de produto novo.
"""
from __future__ import annotations

import random
import time
from datetime import datetime, timezone
from typing import Final

from loguru import logger
from pydantic import ValidationError

from melicrowd.llm.qwen_client import generate_json
from melicrowd.llm.trace import log_decision
from melicrowd.observability.live_tracker import get_tracker
from melicrowd.sellers.actions import (
    audit_inventory,
    auth,
    check_notifications,
    create_product,
    restock,
    suspend,
    update_price,
)
from melicrowd.sellers.models import (
    NotificationDecisionResponse,
    PriceStrategy,
    SellerPersona,
    SessionFocusResponse,
)
from melicrowd.sellers.prompts import DECIDE_SELLER_SESSION, EVALUATE_NOTIFICATION
from melicrowd.sellers.state import SellerSessionState

LOGGER: Final = logger.bind(module="sellers.runner")

#: Mapeamento status interno do seller → "estação" exibida no Live Floor.
SELLER_STATIONS = (
    "seller_idle",
    "seller_login",
    "seller_audit",
    "seller_decide",
    "seller_check_notifications",
    "seller_restock",
    "seller_suspend",
    "seller_create_product",
    "seller_update_price",
    "seller_done",
)


async def _decide_focus(state: SellerSessionState) -> SessionFocusResponse:
    """Qwen #1: decide o foco macro da sessão."""
    p = state.seller_persona
    now = datetime.now(timezone.utc)
    prompt = DECIDE_SELLER_SESSION.format(
        owner_name=p.owner_name,
        store_name=p.store_name,
        location_city=p.location_city,
        location_state=p.location_state,
        price_strategy=p.price_strategy.value,
        restock_aggressiveness=p.restock_aggressiveness,
        expansion_rate=p.expansion_rate,
        category_focus=", ".join(p.category_focus),
        current_catalog_size=len(state.inventory),
        min_catalog_size=p.min_catalog_size,
        max_catalog_size=p.max_catalog_size,
        pending_alerts=len(state.pending_alerts),
        datetime_str=now.strftime("%Y-%m-%d %H:%M"),
        weekday=["seg", "ter", "qua", "qui", "sex", "sáb", "dom"][now.weekday()],
    )
    started = time.monotonic()
    try:
        call = await generate_json(prompt)
        resp = SessionFocusResponse.model_validate(call.response)
        log_decision(
            session_id=state.session_id,
            persona_id=state.seller_persona.seller_persona_id,
            node="seller_decide_session",
            prompt=prompt,
            response_parsed=call.response,
            response_raw=call.raw,
            latency_ms=call.latency_ms,
            fallback_used=False,
        )
        state.qwen_calls_count += 1
        return resp
    except (ValidationError, Exception) as exc:  # noqa: BLE001
        elapsed_ms = int((time.monotonic() - started) * 1000)
        LOGGER.warning(
            "decide_focus fallback",
            extra={"error": str(exc)[:200], "latency_ms": elapsed_ms},
        )
        log_decision(
            session_id=state.session_id,
            persona_id=state.seller_persona.seller_persona_id,
            node="seller_decide_session",
            prompt=prompt,
            response_parsed=None,
            response_raw="",
            latency_ms=elapsed_ms,
            fallback_used=True,
            error=str(exc)[:200],
        )
        state.qwen_calls_count += 1
        return _decide_focus_fallback(state)


def _decide_focus_fallback(state: SellerSessionState) -> SessionFocusResponse:
    """Decisão procedural quando Qwen falha."""
    p = state.seller_persona
    catalog = len(state.inventory)
    alerts = len(state.pending_alerts)

    if alerts >= 3:
        focus = "restock"
    elif catalog < p.min_catalog_size:
        focus = "expand"
    elif catalog >= p.max_catalog_size:
        focus = "maintenance"
    elif p.price_strategy == PriceStrategy.AGGRESSIVE and random.random() < 0.3:
        focus = "promo"
    elif random.random() < p.expansion_rate * 0.5:
        focus = "expand"
    else:
        focus = "maintenance"

    create_n = 0
    if focus == "expand" and catalog < p.max_catalog_size:
        create_n = min(p.max_catalog_size - catalog, random.randint(1, 3))
    update_n = random.randint(1, 4) if focus == "promo" else 0

    return SessionFocusResponse(
        focus=focus,  # type: ignore[arg-type]
        create_n_products=create_n,
        update_n_prices=update_n,
        reasoning="fallback procedural",
    )


async def _evaluate_alert(
    state: SellerSessionState, alert_idx: int
) -> NotificationDecisionResponse:
    """Qwen #2: decide ação pra cada alerta de estoque."""
    alert = state.pending_alerts[alert_idx]
    p = state.seller_persona
    prompt = EVALUATE_NOTIFICATION.format(
        owner_name=p.owner_name,
        store_name=p.store_name,
        product_title=alert.product_title,
        current_stock=alert.current_stock,
        threshold=alert.threshold,
        restock_aggressiveness=p.restock_aggressiveness,
        price_strategy=p.price_strategy.value,
    )
    started = time.monotonic()
    try:
        call = await generate_json(prompt)
        resp = NotificationDecisionResponse.model_validate(call.response)
        log_decision(
            session_id=state.session_id,
            persona_id=p.seller_persona_id,
            node="seller_evaluate_notification",
            prompt=prompt,
            response_parsed=call.response,
            response_raw=call.raw,
            latency_ms=call.latency_ms,
            fallback_used=False,
        )
        state.qwen_calls_count += 1
        return resp
    except (ValidationError, Exception) as exc:  # noqa: BLE001
        elapsed_ms = int((time.monotonic() - started) * 1000)
        LOGGER.warning(
            "evaluate_alert fallback",
            extra={"error": str(exc)[:200]},
        )
        log_decision(
            session_id=state.session_id,
            persona_id=p.seller_persona_id,
            node="seller_evaluate_notification",
            prompt=prompt,
            response_parsed=None,
            response_raw="",
            latency_ms=elapsed_ms,
            fallback_used=True,
            error=str(exc)[:200],
        )
        state.qwen_calls_count += 1
        # Fallback: agressividade do vendedor dita ação.
        if random.random() < p.restock_aggressiveness:
            delta = random.randint(30, 150)
            return NotificationDecisionResponse(action="restock", delta=delta, reasoning="fallback")
        return NotificationDecisionResponse(action="ignore", reasoning="fallback")


async def _set_station(worker_id: str | None, station: str) -> None:
    """Atualiza station do worker no LiveAgentTracker."""
    if not worker_id:
        return
    try:
        await get_tracker().update_worker_station(worker_id, station, kind="seller")
    except AttributeError:
        # Compat: se ainda não tem o método novo, ignora.
        pass
    except Exception:  # noqa: BLE001
        pass


async def run_seller_session(
    persona: SellerPersona,
    *,
    worker_id: str | None = None,
) -> SellerSessionState:
    """Executa 1 sessão de vendedor.

    Sequência:
        1. login (auth)
        2. audit_inventory
        3. check_notifications
        4. Qwen decide foco da sessão
        5. Para cada alerta: Qwen decide ação → executa
        6. Se focus expand: cria N produtos novos
        7. Se focus promo: ajusta N preços
        8. finalize
    """
    state = SellerSessionState(seller_persona=persona, worker_id=worker_id)
    LOGGER.info(
        "seller session start",
        extra={
            "session_id": str(state.session_id),
            "store": persona.store_name,
            "strategy": persona.price_strategy.value,
        },
    )

    # 1. Login
    await _set_station(worker_id, "seller_login")
    if not await auth.run(state):
        state.ended_at = datetime.now(timezone.utc)
        return state

    # 2. Audit inventory
    await _set_station(worker_id, "seller_audit")
    await audit_inventory.run(state)

    # 3. Check notifications
    await _set_station(worker_id, "seller_check_notifications")
    await check_notifications.run(state)

    # 4. Qwen: decide foco
    await _set_station(worker_id, "seller_decide")
    focus_resp = await _decide_focus(state)
    state.session_focus = focus_resp.focus
    state.plan_create_n = focus_resp.create_n_products
    state.plan_update_prices_n = focus_resp.update_n_prices

    # 5. Processa alertas pendentes (sempre, independente de foco)
    if state.pending_alerts:
        for i, alert in enumerate(state.pending_alerts):
            decision = await _evaluate_alert(state, i)
            state.notifications_handled += 1
            if decision.action == "restock":
                await _set_station(worker_id, "seller_restock")
                await restock.run(state, product_id=alert.product_id, delta=max(20, decision.delta))
            elif decision.action == "suspend":
                await _set_station(worker_id, "seller_suspend")
                await suspend.run(state, product_id=alert.product_id)
            # action == "ignore" → não faz nada

    # 6. Expand: cria produtos novos
    if state.session_focus == "expand" or focus_resp.create_n_products > 0:
        await _set_station(worker_id, "seller_create_product")
        catalog_room = persona.max_catalog_size - len(state.inventory)
        n_to_create = min(focus_resp.create_n_products, max(0, catalog_room))
        for _ in range(n_to_create):
            await create_product.run(state)

    # 7. Promo: atualiza preços
    if focus_resp.update_n_prices > 0 and state.inventory:
        await _set_station(worker_id, "seller_update_price")
        sample = random.sample(
            state.inventory, k=min(focus_resp.update_n_prices, len(state.inventory))
        )
        for product in sample:
            await update_price.run(state, product_id=product.product_id)

    # 8. Done
    await _set_station(worker_id, "seller_done")
    state.ended_at = datetime.now(timezone.utc)
    LOGGER.info(
        "seller session end",
        extra={
            "session_id": str(state.session_id),
            "focus": state.session_focus,
            "products_created": state.products_created,
            "restocked": state.products_restocked,
            "suspended": state.products_suspended,
            "prices_updated": state.prices_updated,
            "qwen_calls": state.qwen_calls_count,
            "melisim_calls": state.melisim_calls_count,
        },
    )
    return state


def session_outcome(state: SellerSessionState) -> str:
    """Classifica o outcome da sessão."""
    total_actions = (
        state.products_created
        + state.products_restocked
        + state.products_suspended
        + state.prices_updated
    )
    if state.errors_encountered and total_actions == 0:
        return "error"
    if state.errors_encountered:
        return "partial"
    return "ok"
