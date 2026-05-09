"""Timing realista de comportamento humano.

Inserido entre nós do agente para simular think time, typing speed, page load.
Ajuste por persona: mais digital = mais rápido; idoso = mais lento.
"""
from __future__ import annotations

import asyncio
import random
from typing import Final

from melicrowd.personas.models import Persona

#: Tempo base de pensamento entre ações (segundos).
THINK_BASE_MIN: Final[float] = 2.0
THINK_BASE_MAX: Final[float] = 8.0

#: Velocidade de digitação base (caracteres/segundo).
TYPING_BASE_CPS: Final[float] = 3.0

#: Variação de page load (segundos).
PAGE_LOAD_MIN: Final[float] = 0.3
PAGE_LOAD_MAX: Final[float] = 1.2


async def think_time(persona: Persona) -> None:
    """Tempo de pensamento entre ações na mesma página.

    Modulado por:
    - ``digital_savviness`` baixa → 2x mais lento
    - ``age > 60`` → 1.5x mais lento
    """
    base = random.uniform(THINK_BASE_MIN, THINK_BASE_MAX)
    if persona.digital_savviness < 0.3:
        base *= 2.0
    if persona.age > 60:
        base *= 1.5
    await asyncio.sleep(base)


async def typing_delay(text: str, persona: Persona) -> None:
    """Simula tempo de digitação (ex: digitar query de busca)."""
    chars_per_second = TYPING_BASE_CPS + persona.digital_savviness * 5.0
    duration = max(0.1, len(text) / chars_per_second)
    await asyncio.sleep(duration)


async def page_load_delay() -> None:
    """Variação realista de carregamento de página."""
    await asyncio.sleep(random.uniform(PAGE_LOAD_MIN, PAGE_LOAD_MAX))


async def scroll_delay(persona: Persona) -> None:
    """Tempo de scroll entre listagens (modulado por digital savviness)."""
    base = random.uniform(0.5, 2.0)
    if persona.digital_savviness < 0.3:
        base *= 1.5
    await asyncio.sleep(base)
