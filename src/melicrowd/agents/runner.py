"""Runner — interface high-level para executar 1 sessão completa.

Usa ``graph.astream(stream_mode="updates")`` para que CADA transição entre
nós emita um update. Cada update é replicado no ``LiveAgentTracker`` para
que o WebSocket /ws/agents possa fazer broadcast em tempo real do
posicionamento do agente.

``worker_id``: identificador estável do worker do pool. Quando informado,
o tracker mantém o mesmo dot visual ao longo de várias sessões (e não some
no idle entre elas). Quando ``None``, mantém comportamento legado (entrada
chaveada por session_id).
"""
from __future__ import annotations

import asyncio
import time
from typing import Any
from uuid import UUID, uuid4

from loguru import logger

from melicrowd.agents.graph import build_agent_graph
from melicrowd.agents.state import AgentState
from melicrowd.config import settings
from melicrowd.observability import metrics
from melicrowd.observability.live_tracker import get_tracker
from melicrowd.personas.models import Persona

LOGGER = logger.bind(module="agents.runner")

QWEN_NODES = frozenset({"decide_session", "evaluate_item", "checkout_decision", "write_review"})


async def run_session(
    persona: Persona,
    *,
    session_id: UUID | None = None,
    checkpointer: Any | None = None,
    worker_id: str | None = None,
) -> AgentState:
    """Roda 1 sessão completa para a ``persona`` informada.

    A cada step do grafo (cada nó executado), atualiza o
    ``LiveAgentTracker`` para que o WebSocket faça broadcast.

    Args:
        persona: persona alocada para esta sessão.
        session_id: UUID da sessão. Default: novo UUID4.
        checkpointer: ``BaseCheckpointSaver``. Default: ``MemorySaver``.
        worker_id: ID estável do worker do pool (ex.: ``agent-007``).
            Quando passado, todas as upserts usam essa chave para que o
            mesmo dot persista no Live Floor entre sessões.

    Returns:
        ``AgentState`` final (com outcome e métricas preenchidos).
    """
    sid = session_id or uuid4()
    initial = AgentState(session_id=sid, persona=persona, worker_id=worker_id)
    graph = build_agent_graph(checkpointer)
    config = {"configurable": {"thread_id": str(sid)}, "recursion_limit": 100}
    tracker = get_tracker()

    # Snapshot inicial: agente já visível no Live Floor antes do primeiro nó.
    await tracker.upsert_from_state(initial, worker_id=worker_id, station_override="waiting_pool")

    LOGGER.debug("session start", extra={"session_id": str(sid), "persona_id": str(persona.persona_id)})

    final_state_dict: dict[str, Any] = initial.model_dump()
    last_node_started_at: float | None = None
    last_node_name: str | None = None

    async for chunk in graph.astream(initial.model_dump(), config=config, stream_mode="updates"):
        if not isinstance(chunk, dict):
            continue
        for node_name, update in chunk.items():
            if not isinstance(update, dict):
                continue

            # NOC: registra ENTRADA neste nó (visits++ no in-memory tracker).
            # E registra a duração do nó ANTERIOR (saída), se houver.
            now = time.monotonic()
            if last_node_started_at is not None and last_node_name is not None:
                duration_ms = (now - last_node_started_at) * 1000.0
                metrics.node_duration_seconds.labels(station=last_node_name).observe(
                    duration_ms / 1000.0
                )
                await tracker.record_node_exit(last_node_name, duration_ms=duration_ms)

            metrics.node_visits_total.labels(station=node_name).inc()
            await tracker.record_node_enter(node_name)

            last_node_started_at = now
            last_node_name = node_name

            final_state_dict = {**final_state_dict, **update}
            try:
                tracking_state = AgentState.model_validate(final_state_dict)
            except Exception as exc:  # noqa: BLE001
                metrics.node_errors_total.labels(
                    station=node_name, error_type="state_validation"
                ).inc()
                LOGGER.debug(
                    "could not rebuild AgentState for tracker",
                    extra={"node": node_name, "error": str(exc)[:120]},
                )
                continue

            # NOC: erros capturados no state.errors_encountered viram counter.
            if tracking_state.errors_encountered:
                metrics.node_errors_total.labels(
                    station=node_name, error_type="agent_error"
                ).inc()
                await tracker.record_node_exit(node_name, had_error=True)

            is_qwen = node_name in QWEN_NODES
            await tracker.upsert_from_state(
                tracking_state,
                worker_id=worker_id,
                station_override=node_name,
                is_thinking=is_qwen,
                thinking_progress=1.0 if is_qwen else 0.0,
            )
            await _emit_events_for_step(tracker, tracking_state, node_name, worker_id=worker_id)

            # Demo Live Floor: nós procedurais costumam durar <200ms; sem pausa a bolinha
            # não aparece no quadrante. Nós Qwen já demoram (LLM) — não adicionar delay.
            d = settings.live_floor_fast_node_delay_seconds
            if d > 0.0 and not is_qwen:
                await asyncio.sleep(d)

    # Flush final: registra duração do ÚLTIMO nó visitado (astream não emite
    # mais nada após o nó terminal — sem isso, a duração do `abandon`/`purchased`
    # nunca é capturada).
    if last_node_started_at is not None and last_node_name is not None:
        final_duration_ms = (time.monotonic() - last_node_started_at) * 1000.0
        metrics.node_duration_seconds.labels(station=last_node_name).observe(
            final_duration_ms / 1000.0
        )
        await tracker.record_node_exit(last_node_name, duration_ms=final_duration_ms)

    try:
        final_state = AgentState.model_validate(final_state_dict)
    except Exception:  # noqa: BLE001
        final_state = initial

    LOGGER.info(
        "session end",
        extra={
            "session_id": str(sid),
            "outcome": final_state.outcome.value if final_state.outcome else "unknown",
            "qwen_calls": final_state.qwen_calls_count,
        },
    )
    final_station = (
        "purchased"
        if (final_state.outcome and final_state.outcome.value == "purchased")
        else "abandon"
    )
    await tracker.upsert_from_state(
        final_state, worker_id=worker_id, station_override=final_station
    )
    return final_state


async def _emit_events_for_step(
    tracker: Any, state: AgentState, node_name: str, *, worker_id: str | None = None
) -> None:
    """Traduz a transição do grafo num evento semântico pra UI."""
    persona_name = state.persona.name
    sid = state.session_id

    if node_name == "search":
        query = state.search_queries[-1] if state.search_queries else "?"
        await tracker.push_event(
            session_id=sid,
            persona_name=persona_name,
            event_type="search",
            detail=f'"{query}"',
            station=node_name,
            worker_id=worker_id,
        )
    elif node_name == "add_to_cart" and state.cart:
        last = state.cart[-1]
        await tracker.push_event(
            session_id=sid,
            persona_name=persona_name,
            event_type="cart",
            detail=f"+ {last.title} R$ {last.price:.2f}",
            station=node_name,
            worker_id=worker_id,
        )
    elif node_name == "pay" and state.outcome and state.outcome.value == "purchased":
        await tracker.push_event(
            session_id=sid,
            persona_name=persona_name,
            event_type="purchased",
            detail=f"R$ {state.purchase_total_brl:.2f}",
            station=node_name,
            worker_id=worker_id,
        )
    elif node_name == "abandon" and state.outcome:
        await tracker.push_event(
            session_id=sid,
            persona_name=persona_name,
            event_type="abandon",
            detail=state.outcome.value,
            station=node_name,
            worker_id=worker_id,
        )
    elif node_name in QWEN_NODES and state.decision_trace:
        last = state.decision_trace[-1]
        suffix = " FALLBACK" if last.fallback_used else ""
        await tracker.push_event(
            session_id=sid,
            persona_name=persona_name,
            event_type="qwen",
            detail=f"{node_name} ({last.latency_ms}ms{suffix})",
            station=node_name,
            worker_id=worker_id,
        )
        await tracker.record_qwen_latency(last.latency_ms)
