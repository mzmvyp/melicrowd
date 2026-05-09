"""Kafka publisher — telemetria enriquecida para o broker do MeliSimLake.

Tópicos publicados (decisão #5 do RECON):
- ``events.simulator.session_started``
- ``events.simulator.decision_made``
- ``events.simulator.session_ended``

Schemas: JSON simples (Avro/Schema Registry pode ser adicionado depois;
para bronze do data lake, JSON é suficiente).

Implementação:
- ``aiokafka`` async producer.
- Singleton process-wide (criado pelo lifespan FastAPI ou orchestrator).
- Falha de Kafka NÃO trava a sessão — só loga warning (degradação graceful).
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Final
from uuid import UUID

from aiokafka import AIOKafkaProducer
from loguru import logger

from melicrowd.agents.state import AgentState, DecisionRecord
from melicrowd.config import settings

LOGGER: Final = logger.bind(module="execution.kafka_publisher")


class KafkaPublisher:
    """Async producer para Kafka. Use como singleton via ``get_publisher()``."""

    def __init__(self) -> None:
        self._producer: AIOKafkaProducer | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Cria e inicia o producer subjacente."""
        if self._producer is not None:
            return
        async with self._lock:
            if self._producer is not None:
                return
            self._producer = AIOKafkaProducer(
                bootstrap_servers=settings.kafka_bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                acks="all",
                linger_ms=50,
                # gzip usa zlib (stdlib); lz4 exige pacote `lz4` compatível com aiokafka no runtime.
                compression_type="gzip",
            )
            await self._producer.start()
            LOGGER.info(
                "kafka producer started",
                extra={"bootstrap": settings.kafka_bootstrap_servers},
            )

    async def stop(self) -> None:
        """Flusha e para o producer."""
        if self._producer is None:
            return
        try:
            await self._producer.stop()
        finally:
            self._producer = None
            LOGGER.info("kafka producer stopped")

    async def session_started(self, state: AgentState) -> None:
        """Publica em ``events.simulator.session_started``."""
        payload = {
            "event_id": str(state.session_id),
            "session_id": str(state.session_id),
            "persona_id": str(state.persona.persona_id),
            "persona_class": state.persona.income_class.value,
            "persona_state": state.persona.location_state,
            "persona_age": state.persona.age,
            "started_at": state.started_at.isoformat(),
            "schema_version": "1.0",
        }
        await self._send(settings.kafka_topic_session_started, key=str(state.session_id), value=payload)

    async def decision_made(
        self,
        state: AgentState,
        record: DecisionRecord,
        *,
        prompt_text: str | None = None,
        response_parsed: dict[str, Any] | None = None,
    ) -> None:
        """Publica em ``events.simulator.decision_made``."""
        payload = {
            "event_id": str(record.decision_id),
            "session_id": str(state.session_id),
            "persona_id": str(state.persona.persona_id),
            "node": record.node,
            "latency_ms": record.latency_ms,
            "fallback_used": record.fallback_used,
            "error": record.error,
            "prompt_chars": record.prompt_chars,
            "response_keys": record.response_keys,
            "response_parsed": response_parsed,
            "timestamp": record.timestamp.isoformat(),
            "schema_version": "1.0",
        }
        await self._send(settings.kafka_topic_decision_made, key=str(state.session_id), value=payload)

    async def session_ended(self, state: AgentState) -> None:
        """Publica em ``events.simulator.session_ended``."""
        ended_at = datetime.now(timezone.utc)
        duration = int((ended_at - state.started_at).total_seconds())
        payload = {
            "event_id": str(state.session_id),
            "session_id": str(state.session_id),
            "persona_id": str(state.persona.persona_id),
            "persona_class": state.persona.income_class.value,
            "outcome": state.outcome.value if state.outcome else "unknown",
            "intent": state.session_intent.value if state.session_intent else None,
            "purchase_total_brl": state.purchase_total_brl,
            "duration_seconds": duration,
            "qwen_calls_count": state.qwen_calls_count,
            "qwen_total_latency_ms": state.qwen_total_latency_ms,
            "melisim_calls_count": state.melisim_calls_count,
            "products_viewed": len(state.viewed_products),
            "cart_items": len(state.cart),
            "errors_encountered": len(state.errors_encountered),
            "ended_at": ended_at.isoformat(),
            "schema_version": "1.0",
        }
        await self._send(settings.kafka_topic_session_ended, key=str(state.session_id), value=payload)

    async def _send(self, topic: str, *, key: str, value: dict[str, Any]) -> None:
        if self._producer is None:
            await self.start()
        assert self._producer is not None
        try:
            await self._producer.send_and_wait(topic, key=key, value=value)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning(
                "kafka publish failed (degraded mode)",
                extra={"topic": topic, "error": str(exc)[:200]},
            )


_publisher: KafkaPublisher | None = None


def get_publisher() -> KafkaPublisher:
    """Retorna o publisher singleton."""
    global _publisher  # noqa: PLW0603
    if _publisher is None:
        _publisher = KafkaPublisher()
    return _publisher


def _convert_uuids(d: dict[str, Any]) -> dict[str, Any]:
    """Converte UUIDs em strings para serialização JSON."""
    return {k: (str(v) if isinstance(v, UUID) else v) for k, v in d.items()}
