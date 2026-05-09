"""Políticas de retry para chamadas Qwen via tenacity.

Estratégia:
- Erros transitórios (timeout, connection reset): 3 tentativas com backoff
  exponencial 1s → 2s → 4s.
- JSON inválido: 2 tentativas (Qwen às vezes adiciona ``<thinking>`` tags ou
  texto de explicação antes do JSON; o parser tenta extrair).
- Esgotadas as retries: cai pro fallback procedural (responsabilidade do
  caller, não desta camada).
"""
from __future__ import annotations

import json
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
TRANSIENT_EXCEPTIONS: Final[tuple[type[Exception], ...]] = (
    httpx.TimeoutException,
    httpx.NetworkError,
    httpx.RemoteProtocolError,
    json.JSONDecodeError,
)


def transient_retry() -> AsyncRetrying:
    """Política de retry para erros de transporte/JSON.

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
