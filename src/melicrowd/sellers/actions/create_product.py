"""Action: ``create_product`` — Qwen gera title+description e cria via POST /products."""
from __future__ import annotations

import random
import time

import httpx
from loguru import logger

from melicrowd.execution.melisim_client import get_client
from melicrowd.llm.qwen_client import generate_json
from melicrowd.llm.trace import log_decision
from melicrowd.sellers.models import GeneratedProduct, PriceStrategy
from melicrowd.sellers.prompts import GENERATE_PRODUCT
from melicrowd.sellers.state import SellerSessionState

LOGGER = logger.bind(module="sellers.actions.create_product")

_AGGRESSIVE_PRICE_RANGE = (30.0, 400.0)
_STANDARD_PRICE_RANGE = (80.0, 1500.0)
_PREMIUM_PRICE_RANGE = (300.0, 5000.0)


def _fallback_product(state: SellerSessionState) -> GeneratedProduct:
    p = state.seller_persona
    if p.price_strategy == PriceStrategy.AGGRESSIVE:
        lo, hi = _AGGRESSIVE_PRICE_RANGE
    elif p.price_strategy == PriceStrategy.PREMIUM:
        lo, hi = _PREMIUM_PRICE_RANGE
    else:
        lo, hi = _STANDARD_PRICE_RANGE
    category = p.category_focus[0] if p.category_focus else "geral"
    n = random.randint(1000, 9999)
    return GeneratedProduct(
        title=f"{p.store_name} Item {n}",
        description=f"Produto da categoria {category}. Qualidade verificada pela loja {p.store_name}.",
        category=category,
        price_brl=round(random.uniform(lo, hi), 2),
        initial_stock=random.randint(20, 150),
    )


def _render_prompt(state: SellerSessionState) -> str:
    p = state.seller_persona
    return GENERATE_PRODUCT.format(
        owner_name=p.owner_name,
        store_name=p.store_name,
        location_city=p.location_city,
        location_state=p.location_state,
        category_focus=", ".join(p.category_focus),
        price_strategy=p.price_strategy.value,
    )


async def _generate_via_qwen(state: SellerSessionState) -> GeneratedProduct:
    prompt = _render_prompt(state)
    started = time.monotonic()
    try:
        call = await generate_json(prompt)
        product = GeneratedProduct.model_validate(call.response)
        log_decision(
            session_id=state.session_id,
            persona_id=state.seller_persona.seller_persona_id,
            node="seller_generate_product",
            prompt=prompt,
            response_parsed=call.response,
            response_raw=call.raw,
            latency_ms=call.latency_ms,
            fallback_used=False,
        )
        state.qwen_calls_count += 1
        return product
    except Exception as exc:  # noqa: BLE001
        elapsed_ms = int((time.monotonic() - started) * 1000)
        LOGGER.warning(
            "qwen generate_product fallback",
            extra={"error": str(exc)[:200], "latency_ms": elapsed_ms},
        )
        log_decision(
            session_id=state.session_id,
            persona_id=state.seller_persona.seller_persona_id,
            node="seller_generate_product",
            prompt=prompt,
            response_parsed=None,
            response_raw="",
            latency_ms=elapsed_ms,
            fallback_used=True,
            error=str(exc)[:200],
        )
        state.qwen_calls_count += 1
        return _fallback_product(state)


async def run(state: SellerSessionState) -> bool:
    """Cria 1 produto novo. Returns True se sucedeu."""
    if not state.melisim_user_id or not state.auth_token:
        return False

    generated = await _generate_via_qwen(state)
    client = get_client()
    try:
        product = await client.create_product(
            seller_id=state.melisim_user_id,
            title=generated.title,
            description=generated.description,
            category=generated.category,
            price=generated.price_brl,
            stock=generated.initial_stock,
            auth_token=state.auth_token,
        )
        state.melisim_calls_count += 1
        state.products_created += 1
        LOGGER.info(
            "product created",
            extra={
                "session_id": str(state.session_id),
                "store": state.seller_persona.store_name,
                "title": product.title,
                "price": product.price,
                "stock": product.stock,
            },
        )
        return True
    except httpx.HTTPStatusError as exc:
        LOGGER.debug(
            "create_product rejected",
            extra={"status": exc.response.status_code, "title": generated.title[:60]},
        )
        return False
    except Exception as exc:  # noqa: BLE001
        state.errors_encountered.append(f"create_product: {type(exc).__name__}")
        return False
