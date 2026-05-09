"""Error injection — humanos erram, redes caem.

Tipos:
- ``timeout``: 5% das chamadas HTTP. Caller faz retry.
- ``form_error``: 2% dos submits. Caller preenche errado e tenta de novo.

Configurado via ``settings.timeout_injection_rate`` e
``settings.form_error_injection_rate``.
"""
from __future__ import annotations

import random
from typing import Final

import httpx
from loguru import logger

from melicrowd.config import settings

LOGGER: Final = logger.bind(module="execution.error_injection")


def should_inject_timeout() -> bool:
    """True com probabilidade ``settings.timeout_injection_rate``."""
    return random.random() < settings.timeout_injection_rate


def should_inject_form_error() -> bool:
    """True com probabilidade ``settings.form_error_injection_rate``."""
    return random.random() < settings.form_error_injection_rate


def maybe_raise_timeout(endpoint: str) -> None:
    """Levanta ``httpx.TimeoutException`` se sorteio acontecer.

    Raises:
        httpx.TimeoutException: simulando timeout real.
    """
    if should_inject_timeout():
        LOGGER.debug("injected timeout", extra={"endpoint": endpoint})
        msg = f"injected timeout on {endpoint}"
        raise httpx.TimeoutException(msg)


def maybe_inject_form_payload_corruption(payload: dict[str, object]) -> dict[str, object]:
    """Retorna o payload corrompido com probabilidade configurada.

    Estratégia: troca um campo string por string vazia (caller vai pegar
    422 do servidor e retentar). Não corrompe IDs nem números.
    """
    if not should_inject_form_error():
        return payload
    candidates = [k for k, v in payload.items() if isinstance(v, str) and "id" not in k.lower()]
    if not candidates:
        return payload
    target = random.choice(candidates)
    corrupted = {**payload, target: ""}
    LOGGER.debug("injected form error", extra={"field": target})
    return corrupted
