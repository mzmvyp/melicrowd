"""Cliente DeepSeek-V4-pro (OpenAI-compatible) para o Tech Lead Agent.

Diferente do Qwen (Ollama local), DeepSeek é cloud paid. Cada call tem
custo rastreado em USD. Cliente persiste o cost no objeto Task pra
ele aparecer no dashboard.

Pricing (deepseek-v4-pro, ref. 2026):
- Input cache hit:  $0.07 / 1M tokens
- Input cache miss: $0.27 / 1M tokens
- Output:           $1.10 / 1M tokens
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Final

import httpx
from loguru import logger

from melicrowd.config import settings

LOGGER: Final = logger.bind(module="tech_lead.deepseek_client")

# Preços por 1M tokens (USD). Atualizar quando DeepSeek mudar.
PRICE_INPUT_USD_PER_MTOKEN: Final[float] = 0.27   # cache miss
PRICE_INPUT_CACHED_USD_PER_MTOKEN: Final[float] = 0.07
PRICE_OUTPUT_USD_PER_MTOKEN: Final[float] = 1.10


@dataclass(slots=True)
class DeepSeekResponse:
    """Resultado de uma chamada DeepSeek + métricas de custo."""

    content: str
    parsed_json: dict[str, Any] | None
    prompt_tokens: int
    completion_tokens: int
    cached_tokens: int
    cost_usd: Decimal
    latency_ms: int
    model: str


def estimate_cost(prompt_tokens: int, completion_tokens: int, cached_tokens: int = 0) -> Decimal:
    """Calcula custo em USD a partir das contagens de token."""
    fresh_input = prompt_tokens - cached_tokens
    input_cost = (fresh_input / 1_000_000) * PRICE_INPUT_USD_PER_MTOKEN
    cached_cost = (cached_tokens / 1_000_000) * PRICE_INPUT_CACHED_USD_PER_MTOKEN
    output_cost = (completion_tokens / 1_000_000) * PRICE_OUTPUT_USD_PER_MTOKEN
    return Decimal(f"{input_cost + cached_cost + output_cost:.6f}")


async def generate_json(
    *,
    system_prompt: str,
    user_prompt: str,
    timeout: float = 60.0,
    temperature: float = 0.3,
    max_tokens: int = 2000,
) -> DeepSeekResponse:
    """Chama DeepSeek e retorna JSON parseado + custo da chamada.

    Args:
        system_prompt: persona/contexto fixo (vai no role=system).
        user_prompt: instrução específica da call.
        timeout: timeout HTTPX.
        temperature: 0-1. JSON tarefa = 0.3-0.5 (baixa pra schema, alguma criatividade).
        max_tokens: limite de output.

    Raises:
        httpx.HTTPStatusError: erro de rede / quota / chave inválida.
        ValueError: API retornou resposta sem JSON parseável.
    """
    if not settings.deepseek_api_key:
        msg = "MELICROWD_DEEPSEEK_API_KEY não configurado"
        raise ValueError(msg)

    payload = {
        "model": settings.deepseek_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
    }
    url = f"{settings.deepseek_base_url.rstrip('/')}/chat/completions"

    started = time.monotonic()
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        body = response.json()
    elapsed_ms = int((time.monotonic() - started) * 1000)

    content = body.get("choices", [{}])[0].get("message", {}).get("content", "")
    usage = body.get("usage", {})
    prompt_tokens = int(usage.get("prompt_tokens", 0))
    completion_tokens = int(usage.get("completion_tokens", 0))
    cached_tokens = int(
        usage.get("prompt_cache_hit_tokens", 0) or usage.get("cached_tokens", 0) or 0
    )
    cost = estimate_cost(prompt_tokens, completion_tokens, cached_tokens)

    parsed: dict[str, Any] | None = None
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        # Tenta extrair primeiro objeto JSON da string
        start = content.find("{")
        end = content.rfind("}")
        if 0 <= start < end:
            try:
                parsed = json.loads(content[start : end + 1])
            except json.JSONDecodeError:
                LOGGER.warning(f"deepseek returned non-JSON content. snippet={content[:500]!r}")
        else:
            LOGGER.warning(f"deepseek content has no JSON braces. snippet={content[:500]!r}")

    LOGGER.info(
        "deepseek call",
        extra={
            "model": settings.deepseek_model,
            "latency_ms": elapsed_ms,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cached_tokens": cached_tokens,
            "cost_usd": float(cost),
        },
    )
    return DeepSeekResponse(
        content=content,
        parsed_json=parsed,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cached_tokens=cached_tokens,
        cost_usd=cost,
        latency_ms=elapsed_ms,
        model=settings.deepseek_model,
    )
