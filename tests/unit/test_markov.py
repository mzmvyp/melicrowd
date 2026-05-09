"""Testes da Markov chain modulada por persona."""
from __future__ import annotations

from uuid import uuid4

import numpy as np

from melicrowd.execution.markov import (
    BASE_MATRIX,
    N_STATES,
    STATES,
    get_persona_matrix,
    next_state,
)
from melicrowd.personas.models import IncomeClass, Persona


def _persona(**overrides: object) -> Persona:
    base: dict[str, object] = {
        "persona_id": uuid4(),
        "name": "Test",
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
        "digital_savviness": 0.5,
        "avg_session_duration_min": 15,
        "weekly_visit_frequency": 3,
        "preferred_categories": ["x"],
        "abandonment_likelihood": 0.5,
        "review_likelihood": 0.3,
    }
    base.update(overrides)
    return Persona(**base)  # type: ignore[arg-type]


def test_base_matrix_is_square_and_normalized() -> None:
    assert BASE_MATRIX.shape == (N_STATES, N_STATES)
    np.testing.assert_allclose(BASE_MATRIX.sum(axis=1), np.ones(N_STATES), atol=1e-9)


def test_persona_matrix_rows_sum_to_one() -> None:
    matrix = get_persona_matrix(_persona(price_sensitivity=0.9))
    np.testing.assert_allclose(matrix.sum(axis=1), np.ones(N_STATES), atol=1e-9)


def test_high_price_sensitivity_increases_compare() -> None:
    base = BASE_MATRIX[STATES.index("product_detail"), STATES.index("compare")]
    matrix = get_persona_matrix(_persona(price_sensitivity=0.95))
    boosted = matrix[STATES.index("product_detail"), STATES.index("compare")]
    assert boosted > base


def test_high_abandonment_increases_exit() -> None:
    base = BASE_MATRIX[STATES.index("product_detail"), STATES.index("exit")]
    matrix = get_persona_matrix(_persona(abandonment_likelihood=0.95))
    boosted = matrix[STATES.index("product_detail"), STATES.index("exit")]
    assert boosted > base


def test_next_state_returns_valid_state() -> None:
    p = _persona()
    s = next_state("home", p)
    assert s in STATES
