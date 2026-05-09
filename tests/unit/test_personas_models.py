"""Testes do schema Persona (Pydantic)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from melicrowd.personas.models import IncomeClass, Persona


def _valid_persona_payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "name": "Camila Mendes",
        "age": 32,
        "gender": "F",
        "location_state": "SP",
        "location_city": "São Paulo",
        "income_class": "B",
        "occupation": "Designer Gráfica",
        "interests": ["moda", "viagens", "cinema"],
        "purchase_drivers": ["preço", "marca"],
        "price_sensitivity": 0.5,
        "brand_loyalty": 0.6,
        "risk_tolerance": 0.4,
        "digital_savviness": 0.8,
        "avg_session_duration_min": 15,
        "weekly_visit_frequency": 4,
        "preferred_categories": ["moda", "beleza"],
        "abandonment_likelihood": 0.4,
        "review_likelihood": 0.5,
    }
    base.update(overrides)
    return base


def test_persona_creates_with_valid_payload() -> None:
    p = Persona(**_valid_persona_payload())  # type: ignore[arg-type]
    assert p.name == "Camila Mendes"
    assert p.income_class == IncomeClass.B
    assert p.location_state == "SP"


def test_persona_rejects_invalid_age() -> None:
    with pytest.raises(ValidationError):
        Persona(**_valid_persona_payload(age=10))  # type: ignore[arg-type]


def test_persona_rejects_invalid_state() -> None:
    with pytest.raises(ValidationError):
        Persona(**_valid_persona_payload(location_state="ZZ"))  # type: ignore[arg-type]


def test_persona_normalizes_state_to_upper() -> None:
    p = Persona(**_valid_persona_payload(location_state="sp"))  # type: ignore[arg-type]
    assert p.location_state == "SP"


def test_persona_rejects_invalid_gender() -> None:
    with pytest.raises(ValidationError):
        Persona(**_valid_persona_payload(gender="X"))  # type: ignore[arg-type]


def test_persona_rejects_too_few_interests() -> None:
    with pytest.raises(ValidationError):
        Persona(**_valid_persona_payload(interests=["um", "dois"]))  # type: ignore[arg-type]


def test_persona_rejects_invalid_probability() -> None:
    with pytest.raises(ValidationError):
        Persona(**_valid_persona_payload(price_sensitivity=1.5))  # type: ignore[arg-type]


def test_persona_dedupes_list_items() -> None:
    p = Persona(
        **_valid_persona_payload(
            interests=["Moda", "moda", "Viagens", "Cinema"],
        )  # type: ignore[arg-type]
    )
    # First wins; case-insensitive dedup.
    assert p.interests == ["Moda", "Viagens", "Cinema"]


def test_persona_strips_whitespace() -> None:
    p = Persona(**_valid_persona_payload(name="  Lucas Almeida  "))  # type: ignore[arg-type]
    assert p.name == "Lucas Almeida"
