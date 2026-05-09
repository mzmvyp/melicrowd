"""Redis-backed checkpointer para LangGraph (TTL automático).

LangGraph 0.2.x espera um ``BaseCheckpointSaver`` com métodos
``aget_tuple``, ``aput``, ``alist``, ``aput_writes``. Esta implementação
serializa o ``Checkpoint`` via ``pickle`` (LangGraph já faz isso
internamente em outros savers) e armazena em Redis com TTL.

Por que custom em vez de ``langgraph-checkpoint-redis``: a 0.2.x ainda
tem o pacote em flux e queremos controle total do TTL e do prefix das
keys.
"""
from __future__ import annotations

import pickle
from collections.abc import AsyncIterator, Sequence
from typing import Any

from loguru import logger
from redis.asyncio import Redis

from melicrowd.config import settings

LOGGER = logger.bind(module="agents.checkpointer")

CHECKPOINT_PREFIX = "melicrowd:checkpoint"
WRITES_PREFIX = "melicrowd:writes"


class RedisCheckpointer:
    """Checkpointer mínimo para LangGraph + Redis com TTL.

    NOTE: Este checkpointer cobre a happy path (1 thread por sessão,
    sem ramificações). Para LangGraph features avançadas (subgraphs,
    branching) extender as queries.
    """

    def __init__(self, redis: Redis, ttl_seconds: int | None = None) -> None:
        self.redis = redis
        self.ttl = ttl_seconds or settings.redis_checkpoint_ttl_seconds

    @classmethod
    async def from_url(cls, url: str | None = None) -> RedisCheckpointer:
        """Constrói a partir de uma URL Redis."""
        client = Redis.from_url(url or settings.redis_url, decode_responses=False)
        return cls(client)

    @staticmethod
    def _checkpoint_key(thread_id: str) -> str:
        return f"{CHECKPOINT_PREFIX}:{thread_id}"

    @staticmethod
    def _writes_key(thread_id: str) -> str:
        return f"{WRITES_PREFIX}:{thread_id}"

    async def aget_tuple(self, config: dict[str, Any]) -> Any | None:
        """Recupera o checkpoint mais recente da thread."""
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            return None
        raw = await self.redis.get(self._checkpoint_key(thread_id))
        if raw is None:
            return None
        return pickle.loads(raw)

    async def aput(
        self,
        config: dict[str, Any],
        checkpoint: Any,
        metadata: Any,
        new_versions: dict[str, Any],
    ) -> dict[str, Any]:
        """Persiste o checkpoint com TTL."""
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            return config
        await self.redis.set(
            self._checkpoint_key(thread_id),
            pickle.dumps((config, checkpoint, metadata, new_versions)),
            ex=self.ttl,
        )
        return config

    async def alist(
        self,
        config: dict[str, Any] | None,
        *,
        filter: dict[str, Any] | None = None,  # noqa: A002
        before: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[Any]:
        """Lista checkpoints (apenas o mais recente, suficiente pro happy path)."""
        if config is None:
            return
        result = await self.aget_tuple(config)
        if result is not None:
            yield result

    async def aput_writes(
        self,
        config: dict[str, Any],
        writes: Sequence[Any],
        task_id: str,
    ) -> None:
        """Persiste writes pendentes (acumula na lista)."""
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            return
        key = self._writes_key(thread_id)
        await self.redis.rpush(key, pickle.dumps((task_id, writes)))
        await self.redis.expire(key, self.ttl)

    async def aclose(self) -> None:
        """Fecha a conexão Redis."""
        await self.redis.aclose()
