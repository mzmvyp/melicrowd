"""Hooks que conectam métricas Prometheus aos eventos do simulador.

Pontos de hook:
- Sessão iniciada / finalizada → counters + histograms.
- Chamada Qwen → counter + latency.
- Chamada Melisim → counter + latency.
- Tick periódico → atualiza gauges (qwen_in_flight, qwen_waiting, active_agents).
"""
from __future__ import annotations

import asyncio
from typing import Final

from loguru import logger

from melicrowd.agents.state import AgentState, DecisionRecord
from melicrowd.llm.pool import get_pool as get_qwen_pool
from melicrowd.observability import metrics

LOGGER: Final = logger.bind(module="observability.hooks")


def on_session_started(state: AgentState) -> None:
    """Increment counter de sessões iniciadas."""
    metrics.sessions_started_total.labels(
        persona_class=state.persona.income_class.value,
        intent=state.session_intent.value if state.session_intent else "unknown",
    ).inc()


def on_session_completed(state: AgentState) -> None:
    """Increment counter + observe histograms ao final da sessão."""
    outcome = state.outcome.value if state.outcome else "error"
    metrics.sessions_completed_total.labels(outcome=outcome).inc()
    duration = (state.last_action_at - state.started_at).total_seconds() if state.started_at else 0
    metrics.session_duration_seconds.labels(outcome=outcome).observe(duration)
    metrics.cart_value_brl.labels(outcome=outcome).observe(state.purchase_total_brl)


def on_qwen_call(record: DecisionRecord) -> None:
    """Increment Qwen call counter + observe latency."""
    metrics.qwen_calls_total.labels(
        node=record.node,
        fallback_used=str(record.fallback_used).lower(),
    ).inc()
    metrics.qwen_latency_seconds.labels(node=record.node).observe(record.latency_ms / 1000.0)
    if record.error:
        metrics.qwen_errors_total.labels(error_type=record.error.split(":", 1)[0]).inc()


def on_melisim_call(endpoint: str, status_code: int, latency_seconds: float) -> None:
    """Increment Melisim counter + observe latency."""
    metrics.melisim_calls_total.labels(
        endpoint=endpoint,
        status=str(status_code),
    ).inc()
    metrics.melisim_latency_seconds.labels(endpoint=endpoint).observe(latency_seconds)


async def gauge_refresh_loop(interval: float = 5.0) -> None:
    """Loop periódico que atualiza gauges (Qwen pool stats + active_agents).

    Inicia com lifespan da API. Para no shutdown.
    """
    LOGGER.info("gauge refresh loop starting", extra={"interval": interval})
    # Import tardio evita ciclo api.state → pool → … → hooks.
    from melicrowd.api.state import get_app_state

    while True:
        try:
            qwen = get_qwen_pool().stats
            metrics.qwen_in_flight.set(qwen["in_flight"])
            metrics.qwen_waiting.set(qwen["waiting"])

            app_state = get_app_state()
            if app_state.pool is not None:
                metrics.active_agents.set(app_state.pool.active_agents)
            else:
                metrics.active_agents.set(0)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("gauge refresh failed", extra={"error": str(exc)[:120]})
        await asyncio.sleep(interval)
