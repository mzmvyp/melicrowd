"""Cliente Qwen — wrapper assíncrono em torno de ``langchain-ollama``.

Expõe ``generate_json()`` que:
1. Adquire vaga do ``QwenPool`` (semaphore).
2. Chama Qwen com ``format=json`` (Ollama-native JSON enforcement).
3. Parse com ``json.loads`` + retries via tenacity.
4. Mede latência e registra trace básico.

Erros transitórios sobem após 3 tentativas. Caller é responsável pelo fallback.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Final

import httpx
from loguru import logger

from melicrowd.config import settings
from melicrowd.llm.pool import QwenPool, get_pool
from melicrowd.llm.retry import transient_retry

LOGGER: Final = logger.bind(module="llm.qwen_client")


@dataclass(slots=True)
class QwenCall:
    """Resultado de uma chamada Qwen.

    Atributos:
        response: payload JSON parseado em dict.
        raw: texto cru da resposta (debug).
        latency_ms: tempo total da chamada em ms (inclui espera no semaphore).
        attempts: número de tentativas usadas (1 = sem retry).
    """

    response: dict[str, Any]
    raw: str
    latency_ms: int
    attempts: int


async def generate_json(
    prompt: str,
    *,
    pool: QwenPool | None = None,
    timeout: float | None = None,
) -> QwenCall:
    """Chama Qwen e retorna JSON parseado.

    Args:
        prompt: prompt completo (já preenchido com placeholders).
        pool: pool semaphore. Default: singleton ``get_pool()``.
        timeout: timeout em segundos. Default: ``settings.qwen_timeout_seconds``.

    Returns:
        ``QwenCall`` com response parseado e metadados.

    Raises:
        httpx.HTTPError: erro de rede após 3 retries.
        json.JSONDecodeError: Qwen não retornou JSON válido após 3 retries.
    """
    pool = pool or get_pool()
    timeout = timeout or settings.qwen_timeout_seconds
    started = time.monotonic()
    attempts = 0

    async with pool.acquire():
        async for attempt in transient_retry():
            with attempt:
                attempts = attempt.retry_state.attempt_number
                raw = await _call_ollama(prompt, timeout=timeout)
                parsed = _extract_json(raw)

    elapsed_ms = int((time.monotonic() - started) * 1000)
    LOGGER.debug(
        "qwen call ok",
        extra={"latency_ms": elapsed_ms, "attempts": attempts, "chars_in": len(prompt), "chars_out": len(raw)},
    )
    return QwenCall(response=parsed, raw=raw, latency_ms=elapsed_ms, attempts=attempts)


async def _call_ollama(prompt: str, *, timeout: float) -> str:
    """Chama o endpoint /api/generate do Ollama com format=json.

    Não usamos langchain-ollama aqui pra reduzir overhead — uma chamada HTTP
    direta é suficiente e mais fácil de mockar.
    """
    payload = {
        "model": settings.qwen_model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.7, "num_ctx": 8192},
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{settings.qwen_base_url}/api/generate",
            json=payload,
        )
        response.raise_for_status()
        body = response.json()
    return str(body.get("response", ""))


def _extract_json(raw: str) -> dict[str, Any]:
    """Extrai um objeto JSON da resposta crua.

    Tolera ``<thinking>`` tags do Qwen, prefixos/sufixos de explicação,
    e markdown ``\`\`\`json``. Estratégia: tentar parse direto; se falhar,
    procurar a primeira ``{`` e a última ``}``.
    """
    raw = raw.strip()
    try:
        result = json.loads(raw)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # Fallback: extrai do primeiro { ao último }.
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        candidate = raw[start : end + 1]
        result = json.loads(candidate)
        if isinstance(result, dict):
            return result
        msg = "Qwen returned JSON array, not object"
        raise json.JSONDecodeError(msg, raw, start)

    msg = f"no JSON object found in Qwen response: {raw[:200]!r}"
    raise json.JSONDecodeError(msg, raw, 0)
