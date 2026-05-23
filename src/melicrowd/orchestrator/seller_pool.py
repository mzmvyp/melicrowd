"""SellerPool — pool dedicado a workers vendedores.

Reusa muito do ``AgentPool`` (buyers) mas com SellerScheduler e prefix
``seller-`` no worker_id pra distinguir no LiveAgentTracker.
"""
from __future__ import annotations

import asyncio
from typing import Final

from loguru import logger

from melicrowd.observability.live_tracker import get_tracker
from melicrowd.orchestrator.seller_scheduler import SellerScheduler

LOGGER: Final = logger.bind(module="orchestrator.seller_pool")


class SellerPool:
    """Pool async de workers vendedores."""

    def __init__(
        self,
        target_size: int = 5,
        scheduler: SellerScheduler | None = None,
    ) -> None:
        self._target_size = target_size
        self._scheduler = scheduler or SellerScheduler()
        self._tasks: set[asyncio.Task[None]] = set()
        self._shutdown_event = asyncio.Event()
        self._stopped = False
        self._next_worker_seq = 0
        self._worker_ids: set[str] = set()

    @property
    def target_size(self) -> int:
        return self._target_size

    @property
    def active_workers(self) -> int:
        return len([t for t in self._tasks if not t.done()])

    @property
    def is_running(self) -> bool:
        return not self._stopped and self.active_workers > 0

    async def start(self) -> None:
        if self._stopped:
            msg = "seller pool was stopped — create new instance"
            raise RuntimeError(msg)
        for _ in range(self._target_size - self.active_workers):
            self._spawn_worker()
        LOGGER.info("seller pool started", extra={"target": self._target_size})

    def _spawn_worker(self) -> None:
        worker_id = f"seller-{self._next_worker_seq:03d}"
        self._next_worker_seq += 1
        self._worker_ids.add(worker_id)
        task = asyncio.create_task(self._worker_loop(worker_id), name=worker_id)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _worker_loop(self, worker_id: str) -> None:
        tracker = get_tracker()
        try:
            await tracker.register_seller_worker(worker_id)
        except AttributeError:
            pass
        try:
            while not self._shutdown_event.is_set():
                try:
                    await tracker.mark_seller_idle(worker_id)
                except AttributeError:
                    pass

                try:
                    final_state = await self._scheduler.run_one(worker_id=worker_id)
                    if final_state is None:
                        LOGGER.warning(
                            "seller scheduler returned None — sleeping 30s",
                            extra={"worker_id": worker_id},
                        )
                        await self._wait_or_shutdown(30.0)
                        continue
                except asyncio.CancelledError:
                    break
                except Exception as exc:  # noqa: BLE001
                    LOGGER.exception(
                        "seller worker crashed",
                        extra={"worker_id": worker_id, "error": str(exc)[:200]},
                    )

                if self.active_workers > self._target_size:
                    break

                try:
                    await tracker.mark_seller_idle(worker_id)
                except AttributeError:
                    pass
                await self._wait_or_shutdown(self._scheduler.session_recycle_wait)
        finally:
            try:
                await tracker.unregister_seller_worker(worker_id)
            except AttributeError:
                pass

    async def _wait_or_shutdown(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self._shutdown_event.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            pass

    async def resize(self, new_size: int) -> int:
        if new_size < 0:
            msg = "new_size must be >= 0"
            raise ValueError(msg)
        old = self._target_size
        self._target_size = new_size
        for _ in range(max(0, new_size - self.active_workers)):
            self._spawn_worker()
        LOGGER.info("seller pool resized", extra={"from": old, "to": new_size})
        return self.active_workers

    async def shutdown(self, timeout: float = 30.0) -> None:
        if self._stopped:
            return
        self._stopped = True
        self._shutdown_event.set()
        LOGGER.info("seller pool shutdown initiated", extra={"active": len(self._tasks)})
        if self._tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._tasks, return_exceptions=True),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                for task in self._tasks:
                    task.cancel()
                await asyncio.gather(*self._tasks, return_exceptions=True)

        tracker = get_tracker()
        for worker_id in list(self._worker_ids):
            try:
                await tracker.unregister_seller_worker(worker_id)
            except AttributeError:
                pass
        self._worker_ids.clear()
        LOGGER.info("seller pool shutdown complete")
