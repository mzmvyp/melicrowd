"""Testes do QwenPool — semaphore async."""
from __future__ import annotations

import asyncio

import pytest

from melicrowd.llm.pool import QwenPool


@pytest.mark.asyncio
async def test_pool_limits_concurrency() -> None:
    pool = QwenPool(max_concurrent=2)
    in_flight_max = 0

    async def task() -> None:
        nonlocal in_flight_max
        async with pool.acquire():
            in_flight_max = max(in_flight_max, pool.in_flight)
            await asyncio.sleep(0.05)

    await asyncio.gather(*[task() for _ in range(10)])
    assert in_flight_max <= 2
    assert pool.in_flight == 0
    assert pool.waiting == 0


@pytest.mark.asyncio
async def test_pool_stats_shape() -> None:
    pool = QwenPool(max_concurrent=4)
    stats = pool.stats
    assert stats["max_concurrent"] == 4
    assert stats["in_flight"] == 0
    assert stats["waiting"] == 0


@pytest.mark.asyncio
async def test_pool_releases_on_exception() -> None:
    pool = QwenPool(max_concurrent=1)

    async def failing_task() -> None:
        async with pool.acquire():
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await failing_task()

    assert pool.in_flight == 0
    assert pool.waiting == 0


@pytest.mark.asyncio
async def test_cancel_while_holding_slot_does_not_make_waiting_negative() -> None:
    """Cancelamento da task que já pegou vaga não deve decrementar _waiting global.

    Bug antigo: ``except BaseException`` fazia ``if _waiting > 0: _waiting -= 1``
    mesmo quando a task já tinha saído da fila ao entrar no semáforo. Se outra
    task estava esperando, o contador ia para -1 (ou pior sob carga).
    """
    pool = QwenPool(max_concurrent=1)
    holder_ready = asyncio.Event()

    async def holder() -> None:
        async with pool.acquire():
            holder_ready.set()
            await asyncio.sleep(60)

    async def waiter() -> None:
        async with pool.acquire():
            pass

    h = asyncio.create_task(holder())
    await asyncio.wait_for(holder_ready.wait(), timeout=2.0)
    w = asyncio.create_task(waiter())
    await asyncio.sleep(0.05)
    assert pool.waiting >= 1

    h.cancel()
    with pytest.raises(asyncio.CancelledError):
        await h

    await asyncio.wait_for(w, timeout=2.0)
    assert pool.waiting == 0
    assert pool.in_flight == 0
