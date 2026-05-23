"""AgentPool — N workers concorrentes rodando sessões em loop.

Cada worker tem ``worker_id`` estável (``agent-XXX``, contador monotônico)
e fica registrado no ``LiveAgentTracker`` durante TODA a vida útil — em
``idle`` no waiting_pool entre sessões, em ``in_session`` durante o grafo.

Isso é o que permite à UI (Live Floor) mostrar "100 dots fixos" e medir
ocupação (busy vs idle) em vez de só "quantos têm sessão no ar agora".

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
from melicrowd.observability.live_tracker import get_tracker
from melicrowd.orchestrator.scheduler import SessionScheduler

LOGGER: Final = logger.bind(module="orchestrator.pool")


class AgentPool:
    """Pool async de workers que rodam sessões em loop, com worker_id estável."""

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
        self._next_worker_seq = 0
        self._worker_ids: set[str] = set()

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
        worker_id = f"agent-{self._next_worker_seq:03d}"
        self._next_worker_seq += 1
        self._worker_ids.add(worker_id)
        task = asyncio.create_task(self._worker_loop(worker_id), name=worker_id)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _worker_loop(self, worker_id: str) -> None:
        """Loop infinito de UM worker. Para apenas em ``shutdown_event``."""
        tracker = get_tracker()
        await tracker.register_worker(worker_id)
        try:
            while not self._shutdown_event.is_set():
                # Antes de cada sessão garante estado idle no waiting_pool
                # (caso a sessão anterior tenha terminado em "purchased"/"abandon",
                # o tracker ainda mostraria o último estado).
                await tracker.mark_idle(worker_id)

                try:
                    final_state = await self._scheduler.run_one(worker_id=worker_id)
                    if final_state is None:
                        LOGGER.warning(
                            "scheduler returned None — sleeping 5s",
                            extra={"worker_id": worker_id},
                        )
                        await tracker.mark_idle(worker_id)
                        await self._wait_or_shutdown(5.0)
                        continue
                except asyncio.CancelledError:
                    break
                except Exception as exc:  # noqa: BLE001
                    LOGGER.exception(
                        "worker session crashed",
                        extra={"worker_id": worker_id, "error": str(exc)[:200]},
                    )

                # Decide se continuar ou parar (resize-down).
                if self.active_agents > self._target_size:
                    LOGGER.debug(
                        "worker exiting due to resize-down",
                        extra={"worker_id": worker_id},
                    )
                    break

                # Volta a idle visualmente entre sessões (think time inter-sessão).
                await tracker.mark_idle(worker_id)
                await self._wait_or_shutdown(self._scheduler.session_recycle_wait)
        finally:
            await tracker.unregister_worker(worker_id)

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

        # Garantia: workers cancelados podem não ter conseguido rodar o
        # ``finally`` com ``unregister_worker``. Limpamos o tracker explícito
        # aqui para o Live Floor não acumular fantasmas.
        tracker = get_tracker()
        for worker_id in list(self._worker_ids):
            await tracker.unregister_worker(worker_id)
        self._worker_ids.clear()

        LOGGER.info("pool shutdown complete")
