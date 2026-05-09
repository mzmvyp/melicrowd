"""Personas determinísticas sem LLM — para load tests quando Ollama está offline."""
from __future__ import annotations

from uuid import uuid4

from melicrowd.personas.models import IncomeClass, Persona

# Variação leve para não colidir todas no mesmo perfil.
_STATES = (
    "SP",
    "RJ",
    "MG",
    "RS",
    "PR",
    "SC",
    "BA",
    "PE",
    "CE",
    "DF",
)
_CLASSES = (
    IncomeClass.A,
    IncomeClass.B,
    IncomeClass.B,
    IncomeClass.C,
    IncomeClass.C,
    IncomeClass.C,
    IncomeClass.D,
)


def synthetic_personas(count: int) -> list[Persona]:
    """Gera ``count`` personas válidas (sem chamadas externas)."""
    if count <= 0:
        return []
    out: list[Persona] = []
    for i in range(count):
        st = _STATES[i % len(_STATES)]
        ic = _CLASSES[i % len(_CLASSES)]
        city = "São Paulo" if st == "SP" else "Curitiba" if st == "PR" else "Brasil"
        out.append(
            Persona(
                persona_id=uuid4(),
                name=f"Synthetic Buyer {i + 1}",
                age=22 + (i % 40),
                gender="M" if i % 3 == 0 else "F",
                location_state=st,
                location_city=city,
                income_class=ic,
                occupation="Profissional liberal",
                interests=["ofertas", "marcas", "tecnologia"],
                purchase_drivers=["preço", "entrega rápida"],
                price_sensitivity=0.35 + (i % 10) * 0.05,
                brand_loyalty=0.4,
                risk_tolerance=0.5,
                digital_savviness=0.65 + (i % 5) * 0.05,
                avg_session_duration_min=12 + (i % 20),
                weekly_visit_frequency=2 + (i % 8),
                preferred_categories=["eletrônicos", "casa"],
                abandonment_likelihood=0.55,
                review_likelihood=0.25,
            )
        )
    return out
