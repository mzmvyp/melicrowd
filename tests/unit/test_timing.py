"""Smoke tests para timing helpers."""
from __future__ import annotations

import time
from uuid import uuid4

import pytest

from melicrowd.execution import timing
from melicrowd.personas.models import IncomeClass, Persona


def _persona(**kw: object) -> Persona:
    base: dict[str, object] = {
        "persona_id": uuid4(),
        "name": "Tester",
        "age": 30,
        "gender": "F",
        "location_state": "SP",
        "location_city": "São Paulo",
        "income_class": IncomeClass.B,
        "occupation": "Tester",
        "interests": ["a", "b", "c"],
        "purchase_drivers": ["preço", "marca"],
        "price_sensitivity": 0.5,
        "brand_loyalty": 0.5,
        "risk_tolerance": 0.5,
        "digital_savviness": 0.8,
        "avg_session_duration_min": 15,
        "weekly_visit_frequency": 3,
        "preferred_categories": ["x"],
        "abandonment_likelihood": 0.5,
        "review_likelihood": 0.3,
    }
    base.update(kw)
    return Persona(**base)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_typing_delay_scales_with_text_length() -> None:
    # scale fixo em 1.0: testa a semântica da função, independente do
    # default de settings.human_timing_scale.
    p = _persona()
    short = time.perf_counter()
    await timing.typing_delay("oi", p, scale=1.0)
    short_dt = time.perf_counter() - short

    long_start = time.perf_counter()
    await timing.typing_delay("uma frase muito longa para digitar mais devagar", p, scale=0.2)
    long_dt = time.perf_counter() - long_start

    assert long_dt > short_dt


@pytest.mark.asyncio
async def test_page_load_delay_returns_within_bounds() -> None:
    start = time.perf_counter()
    await timing.page_load_delay(scale=1.0)
    elapsed = time.perf_counter() - start
    assert 0.2 < elapsed < 1.5


@pytest.mark.asyncio
async def test_scale_zero_is_noop() -> None:
    p = _persona()
    start = time.perf_counter()
    await timing.think_time(p, scale=0.0)
    await timing.typing_delay("frase qualquer de teste", p, scale=0.0)
    await timing.page_load_delay(scale=0.0)
    await timing.scroll_delay(p, scale=0.0)
    assert time.perf_counter() - start < 0.05
