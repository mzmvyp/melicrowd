"""Snapshots periódicos de métricas em Postgres (histórico).

Prometheus tem retenção curta (2 dias). Para histórico longo, snapshots vão
pra ``melicrowd.metrics_snapshots`` a cada 1 minuto.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Final
from uuid import uuid4

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from melicrowd.api.state import get_app_state
from melicrowd.db import get_session_factory
from melicrowd.llm.pool import get_pool as get_qwen_pool

LOGGER: Final = logger.bind(module="observability.snapshots")


async def take_snapshot(db: AsyncSession) -> None:
    """Captura snapshot atual e persiste."""
    app_state = get_app_state()
    qwen = get_qwen_pool().stats

    # Conta sessões da última hora.
    sessions_query = await db.execute(
        text(
            "SELECT COUNT(*) AS total, "
            "COUNT(*) FILTER (WHERE outcome='purchased') AS purchased, "
            "COUNT(*) FILTER (WHERE outcome='abandoned_cart') AS abandoned, "
            "AVG(duration_seconds) AS avg_duration "
            "FROM melicrowd.sessions WHERE ended_at > now() - interval '1 hour'"
        )
    )
    row = sessions_query.one()
    total = int(row.total or 0)
    sessions_per_minute = total / 60.0
    conversion = float(row.purchased or 0) / total if total > 0 else 0.0
    abandon_rate = float(row.abandoned or 0) / total if total > 0 else 0.0
    avg_duration = float(row.avg_duration or 0)

    await db.execute(
        text(
            "INSERT INTO melicrowd.metrics_snapshots "
            "(snapshot_id, captured_at, active_agents, sessions_per_minute, "
            " conversion_rate, abandonment_rate, avg_session_duration_seconds, "
            " qwen_p95_latency_ms, qwen_in_flight, custom_metrics) "
            "VALUES (:sid, :ts, :active, :spm, :conv, :abandon, :avg_dur, "
            "        :p95, :qif, :custom)"
        ),
        {
            "sid": uuid4(),
            "ts": datetime.now(timezone.utc),
            "active": app_state.pool.active_agents if app_state.pool else 0,
            "spm": sessions_per_minute,
            "conv": conversion,
            "abandon": abandon_rate,
            "avg_dur": avg_duration,
            "p95": 0.0,  # placeholder — pode ler de Prometheus depois
            "qif": qwen["in_flight"],
            "custom": "{}",
        },
    )
    await db.commit()
    LOGGER.debug(
        "metrics snapshot persisted",
        extra={
            "active": app_state.pool.active_agents if app_state.pool else 0,
            "spm": round(sessions_per_minute, 3),
            "conversion": round(conversion, 3),
        },
    )


async def snapshot_loop(interval: float = 60.0) -> None:
    """Loop que captura snapshot a cada ``interval`` segundos."""
    LOGGER.info("metrics snapshot loop starting", extra={"interval": interval})
    factory = get_session_factory()
    while True:
        try:
            async with factory() as db:
                await take_snapshot(db)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("snapshot failed", extra={"error": str(exc)[:200]})
        await asyncio.sleep(interval)
