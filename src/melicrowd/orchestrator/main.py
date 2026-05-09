"""Entrypoint do orchestrator: AgentPool + Kafka + signal handling.

Comportamento:
1. Configura logging + uvloop.
2. Inicializa Kafka publisher.
3. Cria AgentPool com ``settings.default_agent_count``.
4. Instala signal handlers.
5. Espera SIGTERM/SIGINT.
6. Faz graceful shutdown (drain 30s).
"""
from __future__ import annotations

import asyncio
from typing import Final

from loguru import logger

from melicrowd.config import settings
from melicrowd.execution.kafka_publisher import get_publisher
from melicrowd.logging_setup import configure_logging
from melicrowd.orchestrator.lifecycle import install_signal_handlers
from melicrowd.orchestrator.pool import AgentPool

LOGGER: Final = logger.bind(module="orchestrator.main")


async def _run() -> None:
    LOGGER.info("orchestrator starting", extra={"target_agents": settings.default_agent_count})

    publisher = get_publisher()
    await publisher.start()

    pool = AgentPool()
    shutdown_event = asyncio.Event()
    install_signal_handlers(shutdown_event)
    await pool.start()

    LOGGER.info("orchestrator running — waiting for shutdown signal")
    await shutdown_event.wait()

    LOGGER.info("orchestrator draining")
    await pool.shutdown(timeout=30.0)
    await publisher.stop()
    LOGGER.info("orchestrator stopped cleanly")


def main() -> None:
    """Sync entrypoint — instala uvloop e roda."""
    configure_logging()
    try:
        import uvloop  # type: ignore[import-not-found]

        uvloop.install()
        LOGGER.debug("uvloop installed")
    except ImportError:
        LOGGER.debug("uvloop not available — using default loop")

    asyncio.run(_run())


if __name__ == "__main__":
    main()
