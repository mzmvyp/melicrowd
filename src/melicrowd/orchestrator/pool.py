"""AgentPool — N workers concorrentes rodando sessões em loop.

Cada worker:
1. Pede ao scheduler uma sessão.
2. Executa.
3. Espera ``session_recycle_wait`` segundos.
4. Repete até ``shutdown_event`` ser setado.

Resize:
- ``resize(target)`` ajusta o número de workers ativos.
- Se reduzir: workers extras terminam ao fim da sessão atual (não cortam no meio).
- Se aumentar: spawna novos imediatamente.
"""
from __future__ import annotations

import asyncio
from typing import Final

from loguru import logger

from melicrowd.config import settings
from melicrowd.orchestrator.scheduler import SessionScheduler

LOGGER: Final = logger.bind(module="orchestrator.pool")


class AgentPool:
    """Pool async de workers que rodam sessões em loop."""

    def __init__(
        self,
        target_size: int | None = None,
        scheduler: SessionScheduler | None = None,
    ) -> None:
        self._target_size = target_size or settings.default_agent_count
        self._scheduler = scheduler or SessionScheduler()
        self._tasks: set[asyncio.Task[None]] = set()
        self._shutdown_event = asyncio.Event()
        self._stopped = False

    @property
    def target_size(self) -> int:
        return self._target_size

    @property
    def active_agents(self) -> int:
        return len([t for t in self._tasks if not t.done()])

    @property
    def is_running(self) -> bool:
        return not self._stopped and self.active_agents > 0

    async def start(self) -> None:
        """Spawna ``target_size`` workers."""
        if self._stopped:
            msg = "pool was stopped — create a new instance"
            raise RuntimeError(msg)
        for _ in range(self._target_size - self.active_agents):
            self._spawn_worker()
        LOGGER.info("pool started", extra={"target_size": self._target_size})

    def _spawn_worker(self) -> None:
        task = asyncio.create_task(self._worker_loop(), name=f"agent-{len(self._tasks)}")
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _worker_loop(self) -> None:
        """Loop infinito de UM worker. Para apenas em ``shutdown_event``."""
        while not self._shutdown_event.is_set():
            try:
                final_state = await self._scheduler.run_one()
                if final_state is None:
                    LOGGER.warning("scheduler returned None — sleeping 5s")
                    await self._wait_or_shutdown(5.0)
                    continue
            except asyncio.CancelledError:
                break
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("worker session crashed", extra={"error": str(exc)[:200]})

            # Decide se continuar ou parar (resize-down).
            if self.active_agents > self._target_size:
                LOGGER.debug("worker exiting due to resize-down")
                break

            await self._wait_or_shutdown(self._scheduler.session_recycle_wait)

    async def _wait_or_shutdown(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self._shutdown_event.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            pass

    async def resize(self, new_size: int) -> int:
        """Ajusta o tamanho-alvo do pool."""
        if new_size < 0:
            msg = "new_size must be >= 0"
            raise ValueError(msg)
        old = self._target_size
        self._target_size = new_size
        # Spawna workers se cresceu.
        delta = new_size - self.active_agents
        for _ in range(max(0, delta)):
            self._spawn_worker()
        LOGGER.info("pool resized", extra={"from": old, "to": new_size})
        return self.active_agents

    async def shutdown(self, timeout: float = 30.0) -> None:
        """Graceful shutdown: pede aos workers pra terminar a sessão atual."""
        if self._stopped:
            return
        self._stopped = True
        self._shutdown_event.set()
        LOGGER.info("pool shutdown initiated", extra={"active_workers": len(self._tasks), "timeout": timeout})

        if self._tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._tasks, return_exceptions=True),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                LOGGER.warning("shutdown timeout — cancelling stragglers", extra={"count": len(self._tasks)})
                for task in self._tasks:
                    task.cancel()
                await asyncio.gather(*self._tasks, return_exceptions=True)
        LOGGER.info("pool shutdown complete")
