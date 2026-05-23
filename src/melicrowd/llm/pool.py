"""QwenPool — limite de chamadas concorrentes ao Qwen via async semaphore.

Por que limitar: Qwen 14B em Ollama local satura se ``qwen_max_concurrent``
for alto demais para o GPU — latência p99 explode. O default em ``settings``
(12) é um meio-termo; tune via ``MELICROWD_QWEN_MAX_CONCURRENT``.

Singleton process-wide: criado pelo lifespan do FastAPI e/ou orchestrator
e reutilizado por todos os agentes.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator, Final

from loguru import logger

from melicrowd.config import settings

LOGGER: Final = logger.bind(module="llm.pool")


class QwenPool:
    """Pool com semaphore para chamadas concorrentes ao Qwen.

    Atributos rastreados:
        in_flight: chamadas atualmente executando.
        waiting: chamadas aguardando uma vaga.
        max_concurrent: limite duro do semaphore.
    """

    def __init__(self, max_concurrent: int | None = None) -> None:
        """Inicializa o pool.

        Args:
            max_concurrent: limite de chamadas concorrentes.
                Default: ``settings.qwen_max_concurrent``.
        """
        self.max_concurrent: int = max_concurrent or settings.qwen_max_concurrent
        self._semaphore = asyncio.Semaphore(self.max_concurrent)
        self._in_flight: int = 0
        self._waiting: int = 0
        self._lock = asyncio.Lock()

    @property
    def in_flight(self) -> int:
        """Número de chamadas Qwen em execução agora."""
        return self._in_flight

    @property
    def waiting(self) -> int:
        """Número de chamadas Qwen aguardando vaga no semaphore."""
        return self._waiting

    @property
    def stats(self) -> dict[str, int]:
        """Snapshot de estatísticas do pool."""
        return {
            "in_flight": self._in_flight,
            "waiting": self._waiting,
            "available": self._semaphore._value,  # noqa: SLF001
            "max_concurrent": self.max_concurrent,
        }

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[None]:
        """Adquire uma vaga do pool. Bloqueia até liberar.

        Uso:
            ```python
            async with pool.acquire():
                response = await qwen_call(...)
            ```
        """
        async with self._lock:
            self._waiting += 1
        # Só podemos decrementar ``_waiting`` no ``except`` se ainda não entramos
        # no semáforo. Caso contrário, ao cancelar uma task *dentro* do ``yield``,
        # ``_waiting`` pode ser > 0 por **outras** tasks na fila — decrementar aqui
        # rouba o contador delas e ``qwen_waiting`` no /pool vira negativo.
        entered_semaphore = False
        try:
            async with self._semaphore:
                async with self._lock:
                    self._waiting -= 1
                    entered_semaphore = True
                    self._in_flight += 1
                try:
                    yield
                finally:
                    async with self._lock:
                        self._in_flight -= 1
        except BaseException:
            async with self._lock:
                if not entered_semaphore and self._waiting > 0:
                    self._waiting -= 1
            raise


_global_pool: QwenPool | None = None


def get_pool() -> QwenPool:
    """Retorna o pool singleton process-wide."""
    global _global_pool  # noqa: PLW0603
    if _global_pool is None:
        _global_pool = QwenPool()
        LOGGER.info(
            "qwen pool created",
            extra={"max_concurrent": _global_pool.max_concurrent},
        )
    return _global_pool


def reset_pool() -> None:
    """Reseta o singleton (uso restrito a testes)."""
    global _global_pool  # noqa: PLW0603
    _global_pool = None
