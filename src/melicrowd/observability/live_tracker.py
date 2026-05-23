"""LiveAgentTracker — snapshot in-memory dos workers do pool.

Modelo:
- **worker** é a entidade primeira (vive enquanto o pool estiver de pé).
- Cada worker tem **status estável**:
    ``idle``       — entre sessões (waiting_pool, sem persona)
    ``in_session`` — executando uma sessão (persona + station do grafo)

O ``AgentPool`` registra cada worker no tracker (``register_worker``), mantém
o estado ``idle`` no início e entre sessões (``mark_idle``), e desregistra
ao morrer (``unregister_worker``). O ``runner`` faz ``upsert_from_state``
durante a sessão. O WebSocket /ws/agents lê o snapshot periodicamente.

Chave primária do mapa: ``worker_id`` (string ``agent-XXX``). ``session_id``
ainda é usado para correlação de eventos e como fallback de retrocompat
(quando algum chamador ainda passa só ``state``).
"""
from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Any, Final
from uuid import UUID

from loguru import logger

from melicrowd.agents.state import AgentState

LOGGER: Final = logger.bind(module="observability.live_tracker")

#: Tamanho máximo do buffer de eventos (rolling window).
MAX_EVENTS: Final[int] = 100

#: Cor / archetype para workers em idle (sem persona ainda).
IDLE_PERSONA: Final[dict[str, Any]] = {
    "name": "—",
    "age": 0,
    "city": "",
    "state": "",
    "archetype": "idle",
    "color": "#475569",  # slate-600 (cinza neutro)
    "incomeClass": "",
    "priceSensitivity": 0.0,
    "abandonmentLikelihood": 0.0,
}

#: Persona placeholder para workers SELLER em idle.
IDLE_SELLER_PERSONA: Final[dict[str, Any]] = {
    "name": "—",
    "age": 0,
    "city": "",
    "state": "",
    "archetype": "seller_idle",
    "color": "#F97316",  # laranja — distingue de buyers
    "incomeClass": "",
    "priceSensitivity": 0.0,
    "abandonmentLikelihood": 0.0,
}


@dataclass(slots=True)
class AgentSnapshot:
    """Estado leve de um worker para enviar via WebSocket."""

    id: str  # workerId quando disponível, senão sessionId (retrocompat)
    workerId: str
    sessionId: str
    status: str  # "idle" | "in_session"
    station: str
    prevStation: str | None
    persona: dict[str, Any]
    intent: str | None
    cartTotal: float
    cartItems: list[dict[str, Any]]
    qwenCalls: int
    isThinking: bool
    thinkingProgress: float
    hasError: bool
    rateLimited: bool
    startedAt: float  # ms epoch
    lastActionAt: float
    outcome: str | None
    decisionTrace: list[dict[str, Any]]
    viewedProducts: list[str]
    searchQuery: str | None
    kind: str = "buyer"  # "buyer" | "seller" — distingue tipos de agente


@dataclass(slots=True)
class LiveEvent:
    """Evento individual (search, purchased, abandon, qwen, error, ...)."""

    id: str
    timestamp: float  # ms epoch
    agentId: str
    sessionId: str
    personaName: str
    type: str
    detail: str
    station: str


@dataclass(slots=True)
class LiveStats:
    """Stats acumulados (mantidos pelo tracker, não computados por sessão)."""

    completed: int = 0
    purchased: int = 0
    abandoned: int = 0
    browsedOnly: int = 0
    bounced: int = 0
    error: int = 0
    qwen_calls_total: int = 0
    qwen_call_timestamps: deque[float] = field(default_factory=lambda: deque(maxlen=2000))
    error_timestamps: deque[float] = field(default_factory=lambda: deque(maxlen=2000))
    session_completions: deque[float] = field(default_factory=lambda: deque(maxlen=2000))
    qwen_latencies_recent: deque[int] = field(default_factory=lambda: deque(maxlen=500))
    # Seller-side counters (paralelos aos buyer)
    seller_completed: int = 0
    seller_ok: int = 0
    seller_partial: int = 0
    seller_error: int = 0
    seller_session_completions: deque[float] = field(default_factory=lambda: deque(maxlen=2000))


@dataclass(slots=True)
class NodeStat:
    """Contadores por nó do grafo (consumido pela Topology view).

    Cada estação tem visits totais + janela rolante de timestamps (visitas
    e erros) para cálculo de throughput/min sem precisar de Prometheus.
    """

    visits_total: int = 0
    errors_total: int = 0
    visit_timestamps: deque[float] = field(default_factory=lambda: deque(maxlen=2000))
    error_timestamps: deque[float] = field(default_factory=lambda: deque(maxlen=1000))
    last_durations_ms: deque[float] = field(default_factory=lambda: deque(maxlen=200))


_PERSONA_ARCHETYPE_BY_INCOME = {
    "A": ("premium_buyer", "#A855F7"),
    "B": ("researcher", "#22C55E"),
    "C": ("casual_browser", "#3B82F6"),
    "D": ("bargain_hunter", "#FACC15"),
}


def _persona_to_dict(state: AgentState) -> dict[str, Any]:
    """Converte Persona Pydantic para o shape leve esperado pelo frontend."""
    p = state.persona
    archetype, color = _PERSONA_ARCHETYPE_BY_INCOME.get(
        p.income_class.value, ("casual_browser", "#3B82F6")
    )
    return {
        "name": p.name,
        "age": p.age,
        "city": p.location_city,
        "state": p.location_state,
        "archetype": archetype,
        "color": color,
        "incomeClass": p.income_class.value,
        "priceSensitivity": p.price_sensitivity,
        "abandonmentLikelihood": p.abandonment_likelihood,
    }


def _idle_snapshot(worker_id: str, kind: str = "buyer") -> AgentSnapshot:
    """Cria um snapshot ``idle`` para um worker recém-spawnado.

    Args:
        worker_id: ID estável do worker (``agent-XXX`` ou ``seller-XXX``).
        kind: ``buyer`` (default) ou ``seller`` — controla persona placeholder
            e estação inicial.
    """
    now = time.time() * 1000
    persona = dict(IDLE_SELLER_PERSONA) if kind == "seller" else dict(IDLE_PERSONA)
    station = "seller_idle" if kind == "seller" else "waiting_pool"
    return AgentSnapshot(
        id=worker_id,
        workerId=worker_id,
        sessionId="",
        status="idle",
        station=station,
        prevStation=None,
        persona=persona,
        intent=None,
        cartTotal=0.0,
        cartItems=[],
        qwenCalls=0,
        isThinking=False,
        thinkingProgress=0.0,
        hasError=False,
        rateLimited=False,
        startedAt=now,
        lastActionAt=now,
        outcome=None,
        decisionTrace=[],
        viewedProducts=[],
        searchQuery=None,
        kind=kind,
    )


class LiveAgentTracker:
    """Mantém snapshot in-memory de todos workers do pool + eventos recentes."""

    def __init__(self) -> None:
        # Chave primária = worker_id (string). Quando worker_id não é
        # informado (testes legados / chamadas diretas), usa-se ``session_id``
        # serializado como string — mantém retrocompat.
        self._workers: dict[str, AgentSnapshot] = {}
        self._events: deque[LiveEvent] = deque(maxlen=MAX_EVENTS)
        self._stats = LiveStats()
        self._node_stats: dict[str, NodeStat] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Worker lifecycle (chamado pelo AgentPool)
    # ------------------------------------------------------------------
    async def register_worker(self, worker_id: str) -> None:
        """Registra worker no mapa em estado ``idle`` (waiting_pool)."""
        async with self._lock:
            if worker_id not in self._workers:
                self._workers[worker_id] = _idle_snapshot(worker_id)

    async def unregister_worker(self, worker_id: str) -> None:
        """Remove worker (chamado quando worker termina por shutdown/resize-down)."""
        async with self._lock:
            self._workers.pop(worker_id, None)

    async def mark_idle(self, worker_id: str) -> None:
        """Volta o worker para ``idle`` no waiting_pool (entre sessões)."""
        async with self._lock:
            self._workers[worker_id] = _idle_snapshot(worker_id)

    # ------------------------------------------------------------------
    # Seller worker lifecycle (paralelo ao buyer; mesmo dict _workers)
    # ------------------------------------------------------------------
    async def register_seller_worker(self, worker_id: str) -> None:
        """Registra worker SELLER em estado idle."""
        async with self._lock:
            if worker_id not in self._workers:
                self._workers[worker_id] = _idle_snapshot(worker_id, kind="seller")

    async def unregister_seller_worker(self, worker_id: str) -> None:
        """Remove seller worker."""
        async with self._lock:
            self._workers.pop(worker_id, None)

    async def mark_seller_idle(self, worker_id: str) -> None:
        """Reseta seller worker para idle entre sessões."""
        async with self._lock:
            self._workers[worker_id] = _idle_snapshot(worker_id, kind="seller")

    async def update_worker_station(
        self,
        worker_id: str,
        station: str,
        *,
        kind: str = "buyer",
        persona_name: str | None = None,
    ) -> None:
        """Atualiza ``station`` de um worker sem reconstruir todo o snapshot.

        Usado pelo runner de sellers (loop procedural, sem AgentState completo
        pra alimentar ``upsert_from_state``).
        """
        async with self._lock:
            snap = self._workers.get(worker_id)
            if snap is None:
                # Registra automaticamente se não existe ainda.
                snap = _idle_snapshot(worker_id, kind=kind)
                self._workers[worker_id] = snap
            snap.station = station
            snap.status = "idle" if station.endswith("_idle") else "in_session"
            snap.lastActionAt = time.time() * 1000
            if persona_name and snap.persona.get("name") in ("—", ""):
                snap.persona = dict(snap.persona)
                snap.persona["name"] = persona_name

    # ------------------------------------------------------------------
    # Session updates (chamado pelo runner)
    # ------------------------------------------------------------------
    async def upsert_from_state(
        self,
        state: AgentState,
        *,
        worker_id: str | None = None,
        station_override: str | None = None,
        is_thinking: bool = False,
        thinking_progress: float = 0.0,
    ) -> None:
        """Sincroniza o snapshot do tracker com o ``AgentState`` atual.

        Args:
            worker_id: identificador estável do worker do pool. Quando
                ``None`` (uso legado/testes), usa ``state.session_id`` como
                chave do mapa (entrada efêmera, sem idle).
            station_override: usar este nome como estação (default
                ``state.current_page``).
        """
        key = worker_id if worker_id is not None else str(state.session_id)
        snap = AgentSnapshot(
            id=key,
            workerId=worker_id or "",
            sessionId=str(state.session_id)[:8],
            status="in_session",
            station=station_override or state.current_page,
            prevStation=None,
            persona=_persona_to_dict(state),
            intent=state.session_intent.value if state.session_intent else None,
            cartTotal=state.cart_total(),
            cartItems=[
                {"product_id": i.product_id, "title": i.title, "price": i.price, "quantity": i.quantity}
                for i in state.cart
            ],
            qwenCalls=state.qwen_calls_count,
            isThinking=is_thinking,
            thinkingProgress=thinking_progress,
            hasError=len(state.errors_encountered) > 0,
            rateLimited=False,
            startedAt=state.started_at.timestamp() * 1000,
            lastActionAt=state.last_action_at.timestamp() * 1000,
            outcome=state.outcome.value if state.outcome else None,
            decisionTrace=[
                {
                    "node": d.node,
                    "latencyMs": d.latency_ms,
                    "fallbackUsed": d.fallback_used,
                    "promptChars": d.prompt_chars,
                    "responseKeys": d.response_keys,
                    "timestamp": d.timestamp.timestamp() * 1000,
                }
                for d in state.decision_trace
            ],
            viewedProducts=list(state.viewed_products),
            searchQuery=state.search_queries[-1] if state.search_queries else None,
        )
        async with self._lock:
            self._workers[key] = snap

    async def remove(self, key: UUID | str) -> None:
        """Remove agente do mapa.

        Aceita ``UUID`` (retrocompat: chamada antiga ``remove(session_id)``)
        ou ``str`` (worker_id). Em ambos casos a entrada some completamente —
        para o ciclo "voltar a idle" entre sessões use ``mark_idle``.
        """
        async with self._lock:
            self._workers.pop(str(key), None)

    # ------------------------------------------------------------------
    # Eventos / stats
    # ------------------------------------------------------------------
    async def push_event(
        self,
        *,
        session_id: UUID,
        persona_name: str,
        event_type: str,
        detail: str,
        station: str,
        worker_id: str | None = None,
    ) -> None:
        """Adiciona evento ao buffer (rolling)."""
        ev = LiveEvent(
            id=f"{int(time.time() * 1000)}-{str(session_id)[:8]}",
            timestamp=time.time() * 1000,
            agentId=worker_id or str(session_id),
            sessionId=str(session_id)[:8],
            personaName=persona_name,
            type=event_type,
            detail=detail,
            station=station,
        )
        async with self._lock:
            self._events.appendleft(ev)
            if event_type == "qwen":
                self._stats.qwen_call_timestamps.append(ev.timestamp)
                self._stats.qwen_calls_total += 1
            elif event_type == "error":
                self._stats.error_timestamps.append(ev.timestamp)

    async def record_completion(self, outcome: str) -> None:
        """Atualiza stats acumulados quando uma sessão termina."""
        async with self._lock:
            self._stats.completed += 1
            self._stats.session_completions.append(time.time() * 1000)
            if outcome == "purchased":
                self._stats.purchased += 1
            elif outcome == "abandoned_cart":
                self._stats.abandoned += 1
            elif outcome == "browsed_only":
                self._stats.browsedOnly += 1
            elif outcome == "bounced":
                self._stats.bounced += 1
            else:
                self._stats.error += 1

    async def record_qwen_latency(self, latency_ms: int) -> None:
        """Registra latência Qwen para cálculo de p95."""
        async with self._lock:
            self._stats.qwen_latencies_recent.append(latency_ms)

    async def record_seller_completion(self, outcome: str) -> None:
        """Atualiza stats acumulados quando uma sessão SELLER termina.

        Args:
            outcome: ``ok`` | ``partial`` | ``error``.
        """
        async with self._lock:
            self._stats.seller_completed += 1
            self._stats.seller_session_completions.append(time.time() * 1000)
            if outcome == "ok":
                self._stats.seller_ok += 1
            elif outcome == "partial":
                self._stats.seller_partial += 1
            else:
                self._stats.seller_error += 1

    async def record_node_enter(self, station: str) -> None:
        """Registra entrada num nó (incrementa visits e timestamp).

        Chamado pelo ``runner.py`` quando uma sessão entra em uma estação.
        É independente da duração — duração é registrada por ``record_node_exit``
        quando a sessão sai do nó.
        """
        now = time.time() * 1000
        async with self._lock:
            stat = self._node_stats.setdefault(station, NodeStat())
            stat.visits_total += 1
            stat.visit_timestamps.append(now)

    async def record_node_exit(
        self,
        station: str,
        *,
        duration_ms: float | None = None,
        had_error: bool = False,
    ) -> None:
        """Registra saída de um nó (observa duração / erro).

        ``record_node_enter`` deve ter sido chamado antes — este método
        só anexa observações sem contar visit novamente.
        """
        now = time.time() * 1000
        async with self._lock:
            stat = self._node_stats.setdefault(station, NodeStat())
            if duration_ms is not None:
                stat.last_durations_ms.append(duration_ms)
            if had_error:
                stat.errors_total += 1
                stat.error_timestamps.append(now)

    # Retrocompat: chamada antiga ``record_node_visit`` ainda funciona como enter.
    async def record_node_visit(
        self,
        station: str,
        *,
        had_error: bool = False,
        duration_ms: float | None = None,
    ) -> None:
        """Compat: combina enter + exit numa chamada."""
        await self.record_node_enter(station)
        if duration_ms is not None or had_error:
            await self.record_node_exit(station, duration_ms=duration_ms, had_error=had_error)

    # ------------------------------------------------------------------
    # Snapshot consumido pelo WS
    # ------------------------------------------------------------------
    async def snapshot(self) -> dict[str, Any]:
        """Retorna snapshot completo para envio via WS.

        Shape compatível com o ``useSimulation()`` hook do frontend.
        """
        now_ms = time.time() * 1000
        one_min_ago = now_ms - 60_000
        five_min_ago = now_ms - 300_000

        async with self._lock:
            agents = [asdict(a) for a in self._workers.values()]
            events = [asdict(e) for e in list(self._events)[:30]]

            stats = self._stats
            recent_completions = sum(1 for t in stats.session_completions if t > one_min_ago)
            recent_qwen = sum(1 for t in stats.qwen_call_timestamps if t > one_min_ago)
            recent_errors = sum(1 for t in stats.error_timestamps if t > five_min_ago)

            latencies = sorted(stats.qwen_latencies_recent)
            p95_idx = int(len(latencies) * 0.95)
            p95 = latencies[p95_idx] if 0 <= p95_idx < len(latencies) else 0

            conv = (stats.purchased / stats.completed * 100) if stats.completed > 0 else 0
            abandon = (stats.abandoned / stats.completed * 100) if stats.completed > 0 else 0

            total_workers = len(self._workers)
            busy = sum(1 for a in self._workers.values() if a.status == "in_session")
            idle = total_workers - busy

            # Separação por kind (buyer vs seller) — Live Floor mostra ambos.
            buyer_workers = [a for a in self._workers.values() if a.kind == "buyer"]
            seller_workers = [a for a in self._workers.values() if a.kind == "seller"]
            sellers_busy = sum(1 for a in seller_workers if a.status == "in_session")
            recent_seller_completions = sum(
                1 for t in stats.seller_session_completions if t > one_min_ago
            )

            avg_dur_busy = (
                sum(
                    (now_ms - a.startedAt) / 1000.0
                    for a in self._workers.values()
                    if a.status == "in_session"
                )
                / busy
            ) if busy else 0.0

            # Distribuição de carga por station (útil para gargalo).
            station_load: dict[str, int] = {}
            for a in self._workers.values():
                station_load[a.station] = station_load.get(a.station, 0) + 1

            # Métricas por nó para a Topology view (estilo admin Melisim).
            node_stats: dict[str, dict[str, Any]] = {}
            for station, stat in self._node_stats.items():
                recent_visits = sum(1 for t in stat.visit_timestamps if t > one_min_ago)
                recent_errors = sum(1 for t in stat.error_timestamps if t > one_min_ago)
                durations = sorted(stat.last_durations_ms)
                p95_idx = int(len(durations) * 0.95)
                p95_ms = durations[p95_idx] if 0 <= p95_idx < len(durations) else 0.0
                node_stats[station] = {
                    "visitsTotal": stat.visits_total,
                    "errorsTotal": stat.errors_total,
                    "visitsPerMin": recent_visits,
                    "errorsPerMin": recent_errors,
                    "p95DurationMs": round(p95_ms, 1),
                    "occupancy": station_load.get(station, 0),
                }

        return {
            "agents": agents,
            "events": events,
            "nodeStats": node_stats,
            "kpis": {
                # Mantemos chaves antigas para compat com header existente.
                "activeAgents": busy,
                "sessionsPerMin": recent_completions,
                "conversionRate": f"{conv:.1f}",
                "cartAbandonmentRate": f"{abandon:.1f}",
                "avgSessionDuration": f"{avg_dur_busy:.0f}",
                "qwenCallsPerMin": recent_qwen,
                "p95QwenLatency": f"{p95 / 1000:.1f}",
                "errorsLast5Min": recent_errors,
                # Novos: visão worker.
                "totalWorkers": total_workers,
                "busyWorkers": busy,
                "idleWorkers": idle,
                "utilization": f"{(busy / total_workers * 100) if total_workers else 0:.1f}",
                "stationLoad": station_load,
                # Stats de sellers (subset paralelo aos buyers)
                "sellerTotalWorkers": len(seller_workers),
                "sellerBusyWorkers": sellers_busy,
                "sellerSessionsPerMin": recent_seller_completions,
                "sellerCompleted": stats.seller_completed,
                "sellerOK": stats.seller_ok,
                "sellerPartial": stats.seller_partial,
                "sellerError": stats.seller_error,
                "buyerTotalWorkers": len(buyer_workers),
            },
        }


_tracker: LiveAgentTracker | None = None


def get_tracker() -> LiveAgentTracker:
    """Retorna o singleton process-wide."""
    global _tracker  # noqa: PLW0603
    if _tracker is None:
        _tracker = LiveAgentTracker()
        LOGGER.info("live agent tracker initialized")
    return _tracker


def reset_tracker() -> None:
    """Reseta o singleton (testes)."""
    global _tracker  # noqa: PLW0603
    _tracker = None
