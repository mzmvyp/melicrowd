"""Integração: PersonaRepository contra Postgres real (testcontainers)."""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from melicrowd.personas.models import IncomeClass, Persona
from melicrowd.personas.repository import PersonaRepository


def _persona(income: IncomeClass = IncomeClass.B, state: str = "SP") -> Persona:
    return Persona(
        name=f"Persona {income.value} {state}",
        age=30,
        gender="F",
        location_state=state,
        location_city="São Paulo" if state == "SP" else "Rio de Janeiro",
        income_class=income,
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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_repository_create_and_count(db_session: AsyncSession) -> None:
    repo = PersonaRepository(db_session)
    inserted = await repo.create_batch([_persona() for _ in range(5)])
    await db_session.commit()
    assert inserted == 5
    assert await repo.count() == 5


@pytest.mark.integration
@pytest.mark.asyncio
async def test_repository_filters_by_class_and_state(db_session: AsyncSession) -> None:
    repo = PersonaRepository(db_session)
    personas = [
        _persona(income=IncomeClass.A, state="SP"),
        _persona(income=IncomeClass.A, state="RJ"),
        _persona(income=IncomeClass.B, state="SP"),
        _persona(income=IncomeClass.C, state="SP"),
    ]
    await repo.create_batch(personas)
    await db_session.commit()

    sp_only = await repo.list_paginated(location_state="SP")
    assert len(sp_only) == 3

    a_only = await repo.list_paginated(income_class=IncomeClass.A)
    assert len(a_only) == 2

    a_sp = await repo.list_paginated(income_class=IncomeClass.A, location_state="SP")
    assert len(a_sp) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_repository_get_random(db_session: AsyncSession) -> None:
    repo = PersonaRepository(db_session)
    await repo.create_batch([_persona() for _ in range(10)])
    await db_session.commit()
    sample = await repo.get_random(3)
    assert len(sample) == 3
