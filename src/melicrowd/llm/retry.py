"""Políticas de retry para chamadas Qwen via tenacity.

Estratégia:
- Erros transitórios (timeout, connection reset): 3 tentativas com backoff
  exponencial 1s → 2s → 4s.
- JSON inválido **não** é retentado: com ``format=json`` do Ollama, JSON
  malformado quase sempre significa truncamento por ``num_predict`` — repetir
  raramente resolve e só segura a vaga do semáforo por mais ~3×timeout. O
  caller cai direto no fallback procedural (responsabilidade dele, não desta
  camada).
"""
from __future__ import annotations

from typing import Final

import httpx
from loguru import logger
from tenacity import (
    AsyncRetrying,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

LOGGER: Final = logger.bind(module="llm.retry")


# Exceções consideradas transitórias e elegíveis a retry.
# Nota: ``json.JSONDecodeError`` foi DELIBERADAMENTE removido — ver docstring.
TRANSIENT_EXCEPTIONS: Final[tuple[type[Exception], ...]] = (
    httpx.TimeoutException,
    httpx.NetworkError,
    httpx.RemoteProtocolError,
)


def transient_retry() -> AsyncRetrying:
    """Política de retry para erros de transporte (não para JSON inválido).

    Returns:
        ``AsyncRetrying`` configurado.
    """
    import logging as stdlib_logging
    stdlib_logger = stdlib_logging.getLogger("melicrowd.llm.retry")
    return AsyncRetrying(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(TRANSIENT_EXCEPTIONS),
        reraise=True,
        before_sleep=before_sleep_log(stdlib_logger, stdlib_logging.WARNING),
    )
