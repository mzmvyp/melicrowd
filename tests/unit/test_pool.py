"""Testes do AgentPool — lifecycle e resize."""
from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

import pytest

from melicrowd.agents.state import AgentState, SessionOutcome
from melicrowd.orchestrator.pool import AgentPool
from melicrowd.orchestrator.scheduler import SessionScheduler
from melicrowd.personas.models import IncomeClass, Persona


def _persona() -> Persona:
    return Persona(
        persona_id=uuid4(),
        name="Tester",
        age=30,
        gender="F",
        location_state="SP",
        location_city="São Paulo",
        income_class=IncomeClass.B,
        occupation="Tester",
        interests=["a", "b", "c"],
        purchase_drivers=["preço", "marca"],
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


class _StubScheduler(SessionScheduler):
    def __init__(self, sessions_max: int = 100) -> None:
        super().__init__()
        self.sessions_run = 0
        self._sessions_max = sessions_max

    async def run_one(self) -> AgentState | None:
        self.sessions_run += 1
        if self.sessions_run > self._sessions_max:
            return None
        await asyncio.sleep(0.01)
        return AgentState(persona=_persona(), outcome=SessionOutcome.BROWSED_ONLY)

    @property
    def session_recycle_wait(self) -> float:
        return 0.01


@pytest.mark.asyncio
async def test_pool_starts_target_workers() -> None:
    pool = AgentPool(target_size=3, scheduler=_StubScheduler())
    await pool.start()
    await asyncio.sleep(0.05)
    assert pool.active_agents <= 3
    await pool.shutdown(timeout=2.0)
    assert pool.active_agents == 0


@pytest.mark.asyncio
async def test_pool_resize_grows_workers() -> None:
    pool = AgentPool(target_size=2, scheduler=_StubScheduler())
    await pool.start()
    await asyncio.sleep(0.02)
    await pool.resize(5)
    await asyncio.sleep(0.05)
    assert pool.target_size == 5
    await pool.shutdown(timeout=2.0)


@pytest.mark.asyncio
async def test_pool_shutdown_is_idempotent() -> None:
    pool = AgentPool(target_size=2, scheduler=_StubScheduler())
    await pool.start()
    await pool.shutdown(timeout=1.0)
    # Second shutdown should be no-op.
    await pool.shutdown(timeout=1.0)
    assert pool.active_agents == 0
