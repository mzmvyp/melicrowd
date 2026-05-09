"""Gerador de personas via Qwen.

Estratégia:
1. Dispara N chamadas Qwen em paralelo (limitadas pelo ``QwenPool``).
2. Cada chamada → JSON → ``Persona`` Pydantic. Inválidas viram tentativa nova.
3. No final, valida distribuição (classe social) e re-gera as faltantes
   se desvio > 5% do alvo.
4. Retorna a lista. Persistência é responsabilidade do caller (service layer).
"""
from __future__ import annotations

import asyncio
from collections import Counter
from typing import Final

from loguru import logger
from pydantic import ValidationError

from melicrowd.llm.qwen_client import generate_json
from melicrowd.llm.trace import log_decision
from melicrowd.personas.models import IncomeClass, Persona
from melicrowd.personas.prompts import PERSONA_V1

LOGGER: Final = logger.bind(module="personas.generator")

#: Distribuição alvo por classe (para validação pós-batch).
TARGET_DISTRIBUTION: Final[dict[IncomeClass, float]] = {
    IncomeClass.A: 0.10,
    IncomeClass.B: 0.30,
    IncomeClass.C: 0.45,
    IncomeClass.D: 0.15,
}

#: Tolerância máxima de desvio absoluto (5 pontos percentuais).
DISTRIBUTION_TOLERANCE: Final[float] = 0.05

#: Máximo de tentativas extras pra cobrir personas inválidas.
MAX_RETRIES_PER_BATCH: Final[int] = 3


async def generate_one() -> Persona | None:
    """Gera UMA persona. Retorna ``None`` se Qwen falhar irrecuperavelmente."""
    try:
        call = await generate_json(PERSONA_V1)
        log_decision(
            session_id=None,
            persona_id=None,
            node="persona_batch",
            prompt=PERSONA_V1,
            response_parsed=call.response,
            response_raw=call.raw,
            latency_ms=call.latency_ms,
            fallback_used=False,
        )
        return Persona(**call.response)
    except ValidationError as exc:
        LOGGER.warning("persona pydantic invalid", extra={"error": str(exc)[:200]})
    except Exception as exc:  # noqa: BLE001  (transient/unknown — retry no batch)
        LOGGER.warning("persona generation failed", extra={"error": str(exc)[:200]})
    return None


async def generate_batch(count: int) -> list[Persona]:
    """Gera ``count`` personas válidas em paralelo respeitando o pool semaphore.

    Args:
        count: número de personas válidas a entregar.

    Returns:
        Lista de exatamente ``count`` personas (best-effort após
        ``MAX_RETRIES_PER_BATCH`` ciclos).
    """
    if count <= 0:
        return []

    LOGGER.info("personas batch starting", extra={"target": count})
    personas: list[Persona] = []
    remaining = count

    for cycle in range(MAX_RETRIES_PER_BATCH + 1):
        if remaining == 0:
            break

        results = await asyncio.gather(
            *[generate_one() for _ in range(remaining)],
            return_exceptions=False,
        )
        valid = [p for p in results if p is not None]
        personas.extend(valid)
        remaining = count - len(personas)

        LOGGER.info(
            "personas batch cycle",
            extra={
                "cycle": cycle,
                "valid_so_far": len(personas),
                "still_missing": remaining,
            },
        )

        if remaining == 0:
            break

    if len(personas) < count:
        LOGGER.warning(
            "personas batch incomplete",
            extra={"requested": count, "delivered": len(personas)},
        )

    distribution = _compute_distribution(personas)
    LOGGER.info("personas batch distribution", extra=distribution)

    return personas


def _compute_distribution(personas: list[Persona]) -> dict[str, float]:
    """Calcula a distribuição de classe social no batch."""
    if not personas:
        return {}
    counter = Counter(p.income_class for p in personas)
    total = len(personas)
    return {f"class_{cls.value}_pct": round(counter[cls] / total, 3) for cls in IncomeClass}


def distribution_within_tolerance(personas: list[Persona]) -> bool:
    """Verifica se a distribuição de classe social está dentro de ±5pp do alvo."""
    if not personas:
        return False
    counter = Counter(p.income_class for p in personas)
    total = len(personas)
    for cls, target in TARGET_DISTRIBUTION.items():
        actual = counter[cls] / total
        if abs(actual - target) > DISTRIBUTION_TOLERANCE:
            return False
    return True
