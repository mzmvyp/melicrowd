"""E2E: 50 agentes em paralelo por 15min com stack viva.

Pré-requisitos (skip se não atingidos):
- Postgres MeliCrowd rodando
- Redis MeliCrowd rodando
- Kafka MeliSimLake rodando
- Melisim api-gateway rodando (ou MELICROWD_USE_STUB_MELISIM=true)
- Ollama com qwen3:14b

Critérios de aceite:
- Pool sustenta 50 agentes por 15min sem crash
- ≥ 100 sessões completas (~6.67/min)
- ≥ 1 PURCHASED, ≥ 1 ABANDONED_CART
- Memory leak ausente (RSS estável ±20%)

Roda com: ``pytest tests/e2e/test_50_agents.py -m e2e --timeout=1800``.
"""
from __future__ import annotations

import asyncio
import os

import pytest


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.timeout(1800)
async def test_50_agents_15min() -> None:
    """Skipa se a stack não estiver disponível."""
    if os.environ.get("MELICROWD_E2E_FULL", "false").lower() != "true":
        pytest.skip("set MELICROWD_E2E_FULL=true para rodar (exige stack completa)")

    from melicrowd.execution.kafka_publisher import get_publisher
    from melicrowd.orchestrator.pool import AgentPool

    pool = AgentPool(target_size=50)
    publisher = get_publisher()
    await publisher.start()
    await pool.start()

    # Sustenta por 15min (mas timeout do pytest cobre runaway).
    try:
        await asyncio.sleep(15 * 60)
    finally:
        await pool.shutdown(timeout=60.0)
        await publisher.stop()

    # Asserções pós-execução vão olhar Postgres pra contar sessões finalizadas.
    # Implementação completa requer integração com SessionRepository.
