"""Token bucket rate limiter — respeita o rate limit do api-gateway do Melisim.

Decisão #7 do RECON: como todos os 50 agentes compartilham o mesmo container
(mesmo IP de origem), eles iriam estourar o ``RATE_LIMIT_PER_MINUTE`` (100)
do gateway. Solução: token bucket interno compartilhado entre todos os
agentes.

Implementação:
- Capacidade = ``settings.melisim_rate_limit_per_minute``.
- Refill linear: ``capacity / 60`` tokens/segundo.
- ``acquire()`` aguarda async se não houver token.
"""
from __future__ import annotations

import asyncio
from typing import Final

from loguru import logger

from melicrowd.config import settings

LOGGER: Final = logger.bind(module="execution.rate_limiter")


class TokenBucket:
    """Token bucket assíncrono.

    Atributos:
        capacity: tokens máximos no balde.
        refill_per_second: tokens adicionados por segundo.
    """

    def __init__(self, capacity: int, refill_per_second: float) -> None:
        self.capacity = float(capacity)
        self.refill_per_second = refill_per_second
        self._tokens = float(capacity)
        self._last_refill = asyncio.get_event_loop().time() if asyncio.get_event_loop().is_running() else 0.0
        self._lock = asyncio.Lock()

    async def acquire(self, n: int = 1) -> None:
        """Adquire ``n`` tokens. Bloqueia se não houver."""
        async with self._lock:
            await self._refill()
            if self._tokens >= n:
                self._tokens -= n
                return
            needed = n - self._tokens
            wait = needed / self.refill_per_second
        await asyncio.sleep(wait)
        async with self._lock:
            await self._refill()
            self._tokens = max(0.0, self._tokens - n)

    async def _refill(self) -> None:
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_refill
        if elapsed > 0:
            self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_per_second)
            self._last_refill = now


_global: TokenBucket | None = None


def get_melisim_bucket() -> TokenBucket:
    """Retorna o bucket compartilhado para chamadas Melisim."""
    global _global  # noqa: PLW0603
    if _global is None:
        rpm = settings.melisim_rate_limit_per_minute
        _global = TokenBucket(capacity=rpm, refill_per_second=rpm / 60.0)
        LOGGER.info("melisim token bucket initialized", extra={"rpm": rpm})
    return _global


def reset_bucket() -> None:
    """Reseta o singleton (testes)."""
    global _global  # noqa: PLW0603
    _global = None
