"""Integração: RedisCheckpointer contra Redis real (testcontainers)."""
from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from redis.asyncio import Redis

from melicrowd.agents.checkpointer import RedisCheckpointer


@pytest_asyncio.fixture(scope="module")
async def redis_url() -> AsyncIterator[str]:
    from testcontainers.redis import RedisContainer

    container = RedisContainer("redis:7.4-alpine")
    container.start()
    try:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(6379)
        yield f"redis://{host}:{port}/0"
    finally:
        container.stop()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_checkpointer_put_and_get(redis_url: str) -> None:
    redis = Redis.from_url(redis_url, decode_responses=False)
    cp = RedisCheckpointer(redis, ttl_seconds=10)

    config = {"configurable": {"thread_id": "test-thread-1"}}
    checkpoint = {"foo": "bar"}
    metadata = {"step": 1}

    await cp.aput(config, checkpoint, metadata, {})
    result = await cp.aget_tuple(config)
    assert result is not None
    saved_config, saved_checkpoint, saved_metadata, _ = result
    assert saved_checkpoint == checkpoint
    assert saved_metadata == metadata
    await cp.aclose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_checkpointer_returns_none_for_missing(redis_url: str) -> None:
    redis = Redis.from_url(redis_url, decode_responses=False)
    cp = RedisCheckpointer(redis, ttl_seconds=10)
    result = await cp.aget_tuple({"configurable": {"thread_id": "does-not-exist"}})
    assert result is None
    await cp.aclose()
