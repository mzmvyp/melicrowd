"""Modelos Pydantic da camada Persona.

Persona = perfil realista de comprador brasileiro de e-commerce.
18 campos comportamentais que modulam *todas* as decisões do agente:
- probabilidade de compra
- duração de sessão
- sensibilidade a preço
- propensão a abandonar carrinho
- tendência de escrever review

A geração via Qwen é validada contra este schema; personas inválidas são
descartadas e regeneradas até atingir o batch alvo.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Final, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

#: UFs brasileiras válidas. Persona com state inválido é rejeitada.
VALID_STATES: Final[frozenset[str]] = frozenset(
    {
        "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
        "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
        "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
    }
)


class IncomeClass(str, Enum):
    """Classe social brasileira (proxy para ABEP A/B/C/D).

    Distribuição alvo no batch de 200 personas:
    - A: 10%
    - B: 30%
    - C: 45%
    - D: 15%
    """

    A = "A"
    B = "B"
    C = "C"
    D = "D"


class Persona(BaseModel):
    """Perfil de comprador brasileiro com atributos comportamentais.

    Atributos:
        persona_id: identificador único (UUID4).
        name: nome plausível brasileiro.
        age: idade entre 18 e 85.
        gender: ``F``, ``M`` ou ``NB``.
        location_state: UF (2 letras maiúsculas).
        location_city: cidade brasileira.
        income_class: classe social (A/B/C/D).
        occupation: ocupação profissional.
        interests: lista de 3-8 interesses em português.
        purchase_drivers: 2-5 fatores que motivam compras.
        price_sensitivity: 0.0 (insensível ao preço) → 1.0 (extremamente sensível).
        brand_loyalty: 0.0 → 1.0.
        risk_tolerance: 0.0 (averso) → 1.0 (tolerante).
        digital_savviness: 0.0 (pouco digital) → 1.0 (nativo digital).
        avg_session_duration_min: duração típica de sessão em minutos (2-90).
        weekly_visit_frequency: visitas semanais ao e-commerce (0-21).
        preferred_categories: 1-5 categorias preferidas.
        abandonment_likelihood: probabilidade de abandonar carrinho (0.0-1.0).
        review_likelihood: probabilidade de escrever review pós-compra (0.0-1.0).
        created_at: timestamp de criação (UTC).
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        frozen=False,
    )

    persona_id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=2, max_length=120)
    age: int = Field(ge=18, le=85)
    gender: Literal["F", "M", "NB"]
    location_state: str = Field(min_length=2, max_length=2)
    location_city: str = Field(min_length=2, max_length=120)
    income_class: IncomeClass
    occupation: str = Field(min_length=2, max_length=120)
    interests: list[str] = Field(min_length=3, max_length=8)
    purchase_drivers: list[str] = Field(min_length=2, max_length=5)
    price_sensitivity: float = Field(ge=0.0, le=1.0)
    brand_loyalty: float = Field(ge=0.0, le=1.0)
    risk_tolerance: float = Field(ge=0.0, le=1.0)
    digital_savviness: float = Field(ge=0.0, le=1.0)
    avg_session_duration_min: int = Field(ge=2, le=90)
    weekly_visit_frequency: int = Field(ge=0, le=21)
    preferred_categories: list[str] = Field(min_length=1, max_length=5)
    abandonment_likelihood: float = Field(ge=0.0, le=1.0)
    review_likelihood: float = Field(ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("location_state")
    @classmethod
    def _normalize_state(cls, v: str) -> str:
        """Normaliza para UPPER e valida que é UF brasileira real."""
        upper = v.upper()
        if upper not in VALID_STATES:
            msg = f"location_state {v!r} não é uma UF brasileira válida"
            raise ValueError(msg)
        return upper

    @field_validator("interests", "purchase_drivers", "preferred_categories")
    @classmethod
    def _trim_list_items(cls, v: list[str]) -> list[str]:
        """Remove items vazios e duplicados (preservando ordem)."""
        seen: set[str] = set()
        cleaned: list[str] = []
        for item in v:
            normalized = item.strip()
            if normalized and normalized.lower() not in seen:
                seen.add(normalized.lower())
                cleaned.append(normalized)
        return cleaned
