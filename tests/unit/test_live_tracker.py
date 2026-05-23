"""Testes do LiveAgentTracker (singleton + snapshot + eventos)."""
from __future__ import annotations

from uuid import uuid4

import pytest

from melicrowd.agents.state import AgentState, CartItem, SessionIntent, SessionOutcome
from melicrowd.observability.live_tracker import (
    LiveAgentTracker,
    get_tracker,
    reset_tracker,
)
from melicrowd.personas.models import IncomeClass, Persona


@pytest.fixture(autouse=True)
def _isolate_tracker() -> None:
    reset_tracker()
    yield
    reset_tracker()


def _persona(income: IncomeClass = IncomeClass.B) -> Persona:
    return Persona(
        persona_id=uuid4(),
        name="Tracker Tester",
        age=30,
        gender="F",
        location_state="SP",
        location_city="São Paulo",
        income_class=income,
        occupation="Engineer",
        interests=["a", "b", "c"],
        purchase_drivers=["preço", "qualidade"],
        price_sensitivity=0.5,
        brand_loyalty=0.5,
        risk_tolerance=0.5,
        digital_savviness=0.7,
        avg_session_duration_min=15,
        weekly_visit_frequency=3,
        preferred_categories=["x"],
        abandonment_likelihood=0.5,
        review_likelihood=0.3,
    )


def _state(persona: Persona | None = None, **overrides: object) -> AgentState:
    base = AgentState(persona=persona or _persona())
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


def test_get_tracker_returns_singleton() -> None:
    a = get_tracker()
    b = get_tracker()
    assert a is b


@pytest.mark.asyncio
async def test_upsert_records_agent_in_snapshot() -> None:
    tracker = LiveAgentTracker()
    state = _state()
    await tracker.upsert_from_state(state, station_override="search")
    snap = await tracker.snapshot()
    assert len(snap["agents"]) == 1
    assert snap["agents"][0]["station"] == "search"
    assert snap["agents"][0]["persona"]["name"] == "Tracker Tester"


@pytest.mark.asyncio
async def test_station_override_replaces_current_page() -> None:
    tracker = LiveAgentTracker()
    state = _state()
    state.current_page = "home"
    await tracker.upsert_from_state(state, station_override="evaluate_item")
    snap = await tracker.snapshot()
    assert snap["agents"][0]["station"] == "evaluate_item"


@pytest.mark.asyncio
async def test_remove_kicks_agent_out() -> None:
    tracker = LiveAgentTracker()
    state = _state()
    await tracker.upsert_from_state(state)
    await tracker.remove(state.session_id)
    snap = await tracker.snapshot()
    assert snap["agents"] == []


@pytest.mark.asyncio
async def test_push_event_appears_in_snapshot() -> None:
    tracker = LiveAgentTracker()
    sid = uuid4()
    await tracker.push_event(
        session_id=sid,
        persona_name="Foo Bar",
        event_type="search",
        detail='"iphone 15"',
        station="search",
    )
    snap = await tracker.snapshot()
    assert len(snap["events"]) == 1
    ev = snap["events"][0]
    assert ev["type"] == "search"
    assert ev["detail"] == '"iphone 15"'
    assert ev["personaName"] == "Foo Bar"


@pytest.mark.asyncio
async def test_record_completion_updates_kpis() -> None:
    tracker = LiveAgentTracker()
    await tracker.record_completion("purchased")
    await tracker.record_completion("purchased")
    await tracker.record_completion("abandoned_cart")
    snap = await tracker.snapshot()
    # 2/3 = 66.7% conversion
    assert float(snap["kpis"]["conversionRate"]) == pytest.approx(66.7, abs=0.5)
    assert float(snap["kpis"]["cartAbandonmentRate"]) == pytest.approx(33.3, abs=0.5)


@pytest.mark.asyncio
async def test_qwen_event_increments_counter() -> None:
    tracker = LiveAgentTracker()
    await tracker.push_event(
        session_id=uuid4(),
        persona_name="X",
        event_type="qwen",
        detail="decide_session (1200ms)",
        station="decide_session",
    )
    snap = await tracker.snapshot()
    assert snap["kpis"]["qwenCallsPerMin"] == 1


@pytest.mark.asyncio
async def test_record_qwen_latency_drives_p95() -> None:
    tracker = LiveAgentTracker()
    # 100 latencies of 1000ms + 5 of 5000ms → p95 should land in upper range.
    for _ in range(100):
        await tracker.record_qwen_latency(1000)
    for _ in range(5):
        await tracker.record_qwen_latency(5000)
    snap = await tracker.snapshot()
    assert float(snap["kpis"]["p95QwenLatency"]) >= 1.0


@pytest.mark.asyncio
async def test_persona_archetype_mapped_from_income_class() -> None:
    tracker = LiveAgentTracker()
    a_state = _state(_persona(IncomeClass.A))
    d_state = _state(_persona(IncomeClass.D))
    await tracker.upsert_from_state(a_state)
    await tracker.upsert_from_state(d_state)
    snap = await tracker.snapshot()
    archetypes = {a["persona"]["archetype"] for a in snap["agents"]}
    assert archetypes == {"premium_buyer", "bargain_hunter"}


@pytest.mark.asyncio
async def test_cart_total_propagates_to_snapshot() -> None:
    tracker = LiveAgentTracker()
    state = _state()
    state.cart.append(CartItem(product_id="p1", title="A", price=100.0, quantity=2))
    state.cart.append(CartItem(product_id="p2", title="B", price=50.0, quantity=1))
    await tracker.upsert_from_state(state)
    snap = await tracker.snapshot()
    assert snap["agents"][0]["cartTotal"] == 250.0
    assert len(snap["agents"][0]["cartItems"]) == 2


@pytest.mark.asyncio
async def test_outcome_field_is_serializable() -> None:
    tracker = LiveAgentTracker()
    state = _state()
    state.outcome = SessionOutcome.PURCHASED
    state.session_intent = SessionIntent.PURCHASE
    await tracker.upsert_from_state(state, station_override="purchased")
    snap = await tracker.snapshot()
    assert snap["agents"][0]["outcome"] == "purchased"
    assert snap["agents"][0]["intent"] == "purchase"


# ---------------------------------------------------------------------------
# Worker lifecycle (modelo novo: tracker chaveado por worker_id)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_worker_creates_idle_entry() -> None:
    tracker = LiveAgentTracker()
    await tracker.register_worker("agent-001")
    snap = await tracker.snapshot()
    assert len(snap["agents"]) == 1
    a = snap["agents"][0]
    assert a["workerId"] == "agent-001"
    assert a["status"] == "idle"
    assert a["station"] == "waiting_pool"
    assert a["sessionId"] == ""


@pytest.mark.asyncio
async def test_register_worker_is_idempotent() -> None:
    tracker = LiveAgentTracker()
    await tracker.register_worker("agent-001")
    await tracker.register_worker("agent-001")
    snap = await tracker.snapshot()
    assert len(snap["agents"]) == 1


@pytest.mark.asyncio
async def test_upsert_with_worker_id_marks_busy_and_keeps_key_stable() -> None:
    tracker = LiveAgentTracker()
    await tracker.register_worker("agent-001")
    state = _state()
    await tracker.upsert_from_state(
        state, worker_id="agent-001", station_override="search"
    )
    snap = await tracker.snapshot()
    assert len(snap["agents"]) == 1
    a = snap["agents"][0]
    assert a["workerId"] == "agent-001"
    assert a["status"] == "in_session"
    assert a["station"] == "search"


@pytest.mark.asyncio
async def test_mark_idle_resets_to_waiting_pool() -> None:
    tracker = LiveAgentTracker()
    await tracker.register_worker("agent-001")
    state = _state()
    await tracker.upsert_from_state(
        state, worker_id="agent-001", station_override="pay"
    )
    await tracker.mark_idle("agent-001")
    snap = await tracker.snapshot()
    a = snap["agents"][0]
    assert a["status"] == "idle"
    assert a["station"] == "waiting_pool"
    assert a["sessionId"] == ""


@pytest.mark.asyncio
async def test_unregister_worker_removes_entry() -> None:
    tracker = LiveAgentTracker()
    await tracker.register_worker("agent-001")
    await tracker.unregister_worker("agent-001")
    snap = await tracker.snapshot()
    assert snap["agents"] == []


@pytest.mark.asyncio
async def test_kpis_busy_idle_split_reflects_workers() -> None:
    tracker = LiveAgentTracker()
    await tracker.register_worker("agent-001")
    await tracker.register_worker("agent-002")
    await tracker.register_worker("agent-003")
    # 1 worker em sessão, 2 idle.
    state = _state()
    await tracker.upsert_from_state(
        state, worker_id="agent-001", station_override="search"
    )
    snap = await tracker.snapshot()
    kpis = snap["kpis"]
    assert kpis["totalWorkers"] == 3
    assert kpis["busyWorkers"] == 1
    assert kpis["idleWorkers"] == 2
    assert kpis["activeAgents"] == 1  # alias retrocompat
    # station_load deve refletir a distribuição
    assert kpis["stationLoad"]["waiting_pool"] == 2
    assert kpis["stationLoad"]["search"] == 1
