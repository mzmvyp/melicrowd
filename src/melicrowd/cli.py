"""CLI do MeliCrowd (Typer).

Subcomandos:
- ``personas generate --count N`` — gera N personas via Qwen e persiste no DB.
- ``personas count`` — total de personas no DB.
- ``orchestrator run`` — inicia o pool de agentes (stub Fase 5).
- ``info`` — versão e configuração efetiva.
"""
from __future__ import annotations

import asyncio
import json

import typer
from loguru import logger

from melicrowd import __version__
from melicrowd.config import settings
from melicrowd.db import dispose_engine, get_session_factory
from melicrowd.logging_setup import configure_logging
from melicrowd.personas.repository import PersonaRepository
from melicrowd.personas.service import PersonaService
from melicrowd.personas.synthetic import synthetic_personas

app = typer.Typer(
    name="melicrowd",
    help="MeliCrowd — simulador multi-agente de tráfego realista.",
    no_args_is_help=True,
)

personas_app = typer.Typer(help="Gerenciamento de personas.")
orchestrator_app = typer.Typer(help="Operação do pool de agentes.")
app.add_typer(personas_app, name="personas")
app.add_typer(orchestrator_app, name="orchestrator")


@app.callback()
def _bootstrap() -> None:
    """Inicializa logging antes de qualquer subcomando."""
    configure_logging()


@app.command()
def info() -> None:
    """Imprime versão e configuração efetiva."""
    payload = {
        "version": __version__,
        "qwen_model": settings.qwen_model,
        "qwen_max_concurrent": settings.qwen_max_concurrent,
        "default_agent_count": settings.default_agent_count,
        "melisim_gateway_url": settings.melisim_gateway_url,
        "kafka_bootstrap_servers": settings.kafka_bootstrap_servers,
    }
    typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))


# -----------------------------------------------------------------------------
# Personas
# -----------------------------------------------------------------------------


async def _personas_generate(count: int) -> int:
    factory = get_session_factory()
    async with factory() as session:
        service = PersonaService(session)
        personas = await service.generate_and_persist(count)
    await dispose_engine()
    return len(personas)


@personas_app.command("generate")
def personas_generate(
    count: int = typer.Option(200, "--count", "-n", min=1, max=2000),
) -> None:
    """Gera N personas via Qwen e persiste no Postgres."""
    logger.bind(module="cli.personas").info("personas generate", extra={"count": count})
    delivered = asyncio.run(_personas_generate(count))
    typer.echo(f"✓ {delivered}/{count} personas persistidas")


async def _personas_count() -> int:
    factory = get_session_factory()
    async with factory() as session:
        service = PersonaService(session)
        total = await service.count()
    await dispose_engine()
    return total


@personas_app.command("count")
def personas_count() -> None:
    """Total de personas persistidas."""
    total = asyncio.run(_personas_count())
    typer.echo(f"{total} personas")


async def _personas_seed_synthetic(count: int) -> int:
    personas = synthetic_personas(count)
    factory = get_session_factory()
    async with factory() as session:
        repo = PersonaRepository(session)
        inserted = await repo.create_batch(personas)
        await session.commit()
    await dispose_engine()
    return inserted


@personas_app.command("seed-synthetic")
def personas_seed_synthetic(
    count: int = typer.Option(60, "--count", "-n", min=1, max=2000),
) -> None:
    """Insere personas sintéticas no Postgres (sem Qwen — útil com Ollama offline)."""
    logger.bind(module="cli.personas").info("personas seed-synthetic", extra={"count": count})
    inserted = asyncio.run(_personas_seed_synthetic(count))
    typer.echo(f"✓ {inserted} personas sintéticas persistidas")


# -----------------------------------------------------------------------------
# Orchestrator (stub Fase 5)
# -----------------------------------------------------------------------------


@orchestrator_app.command("run")
def orchestrator_run(
    agents: int = typer.Option(None, "--agents", "-a"),
) -> None:
    """Inicia o pool de agentes (implementação na Fase 5)."""
    n = agents or settings.default_agent_count
    logger.bind(module="cli.orchestrator").info("orchestrator run (stub)", extra={"agents": n})
    typer.echo(f"[stub Fase 5] iniciaria pool com {n} agentes")


if __name__ == "__main__":
    app()
