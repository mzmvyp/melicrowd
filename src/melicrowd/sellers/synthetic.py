"""Personas seller determinísticas — útil para dev/CI sem Qwen.

Gera ``count`` personas SellerPersona com distribuição plausível por
estratégia de preço (aggressive/standard/premium) e categorias brasileiras.
"""
from __future__ import annotations

import random
from uuid import uuid4

from melicrowd.sellers.models import PriceStrategy, SellerPersona

_STATES = ("SP", "RJ", "MG", "RS", "PR", "SC", "BA", "PE", "CE", "DF")
_CITIES = {
    "SP": "São Paulo", "RJ": "Rio de Janeiro", "MG": "Belo Horizonte",
    "RS": "Porto Alegre", "PR": "Curitiba", "SC": "Florianópolis",
    "BA": "Salvador", "PE": "Recife", "CE": "Fortaleza", "DF": "Brasília",
}

_STORE_PREFIXES = (
    "Casa", "Loja", "Mercado", "Empório", "Distribuidora", "Bazar",
    "Comércio", "Shopping", "Outlet", "Center",
)
_STORE_SUFFIXES = (
    "do Brasil", "Premium", "Express", "Plus", "Top", "Pro",
    "& Cia", "Tech", "Style", "Home",
)
_OWNER_NAMES = (
    "Carlos Mendes", "Ana Paula Silva", "Roberto Almeida", "Juliana Costa",
    "Marcos Pereira", "Patrícia Oliveira", "Felipe Rocha", "Camila Souza",
    "Diego Martins", "Renata Lima", "Bruno Fernandes", "Tatiana Ribeiro",
)

_CATEGORY_PROFILES = (
    (PriceStrategy.AGGRESSIVE, ["eletrônicos", "informática"]),
    (PriceStrategy.AGGRESSIVE, ["moda", "calçados"]),
    (PriceStrategy.STANDARD, ["casa", "decoração", "móveis"]),
    (PriceStrategy.STANDARD, ["esporte", "fitness"]),
    (PriceStrategy.STANDARD, ["livros", "papelaria"]),
    (PriceStrategy.STANDARD, ["beleza", "perfumaria"]),
    (PriceStrategy.PREMIUM, ["eletrônicos", "áudio"]),
    (PriceStrategy.PREMIUM, ["moda", "luxo"]),
)


def synthetic_seller_personas(count: int) -> list[SellerPersona]:
    """Gera ``count`` personas seller plausíveis sem chamar LLM."""
    if count <= 0:
        return []
    out: list[SellerPersona] = []
    for i in range(count):
        state = _STATES[i % len(_STATES)]
        strategy, categories = _CATEGORY_PROFILES[i % len(_CATEGORY_PROFILES)]
        prefix = _STORE_PREFIXES[i % len(_STORE_PREFIXES)]
        suffix = _STORE_SUFFIXES[(i * 3) % len(_STORE_SUFFIXES)]
        store_name = f"{prefix} {categories[0].capitalize()} {suffix}"
        owner = _OWNER_NAMES[i % len(_OWNER_NAMES)]

        if strategy == PriceStrategy.AGGRESSIVE:
            restock = round(random.uniform(0.6, 0.95), 2)
            expansion = round(random.uniform(0.4, 0.7), 2)
        elif strategy == PriceStrategy.PREMIUM:
            restock = round(random.uniform(0.4, 0.7), 2)
            expansion = round(random.uniform(0.1, 0.3), 2)
        else:
            restock = round(random.uniform(0.5, 0.8), 2)
            expansion = round(random.uniform(0.2, 0.5), 2)

        out.append(
            SellerPersona(
                seller_persona_id=uuid4(),
                store_name=store_name,
                owner_name=owner,
                location_state=state,
                location_city=_CITIES.get(state, "Capital"),
                category_focus=list(categories),
                price_strategy=strategy,
                restock_aggressiveness=restock,
                expansion_rate=expansion,
                min_catalog_size=random.randint(5, 10),
                max_catalog_size=random.randint(20, 50),
                session_cooldown_min_seconds=random.randint(60, 180),
                session_cooldown_max_seconds=random.randint(300, 900),
            )
        )
    return out
