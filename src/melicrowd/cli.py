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
from melicrowd.sellers.repository import SellerRepository
from melicrowd.sellers.synthetic import synthetic_seller_personas

app = typer.Typer(
    name="melicrowd",
    help="MeliCrowd — simulador multi-agente de tráfego realista.",
    no_args_is_help=True,
)

personas_app = typer.Typer(help="Gerenciamento de personas (buyer).")
sellers_app = typer.Typer(help="Gerenciamento de personas seller (vendedor).")
orchestrator_app = typer.Typer(help="Operação do pool de agentes.")
tech_lead_app = typer.Typer(help="Tech Lead Agent (DeepSeek V4 Pro).")
app.add_typer(personas_app, name="personas")
app.add_typer(sellers_app, name="sellers")
app.add_typer(orchestrator_app, name="orchestrator")
app.add_typer(tech_lead_app, name="tech-lead")


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
# Sellers
# -----------------------------------------------------------------------------


async def _sellers_seed_synthetic(count: int) -> int:
    personas = synthetic_seller_personas(count)
    factory = get_session_factory()
    async with factory() as session:
        repo = SellerRepository(session)
        inserted = await repo.create_batch(personas)
        await session.commit()
    await dispose_engine()
    return inserted


async def _sellers_count() -> int:
    factory = get_session_factory()
    async with factory() as session:
        repo = SellerRepository(session)
        total = await repo.count()
    await dispose_engine()
    return total


@sellers_app.command("seed-synthetic")
def sellers_seed_synthetic(
    count: int = typer.Option(10, "--count", "-n", min=1, max=200),
) -> None:
    """Insere personas seller sintéticas no Postgres (sem Qwen)."""
    logger.bind(module="cli.sellers").info("sellers seed-synthetic", extra={"count": count})
    inserted = asyncio.run(_sellers_seed_synthetic(count))
    typer.echo(f"✓ {inserted} sellers sintéticos persistidos")


@sellers_app.command("count")
def sellers_count() -> None:
    """Total de sellers persistidos."""
    total = asyncio.run(_sellers_count())
    typer.echo(f"{total} sellers")


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


# -----------------------------------------------------------------------------
# Tech Lead Agent
# -----------------------------------------------------------------------------


async def _tech_lead_generate() -> dict | None:
    from melicrowd.tech_lead.service import TechLeadService

    factory = get_session_factory()
    async with factory() as session:
        service = TechLeadService(session)
        task = await service.generate_and_persist()
    await dispose_engine()
    if task is None:
        return None
    return {
        "task_id": str(task.task_id),
        "title": task.title,
        "category": task.category.value,
        "priority": task.priority.value,
        "sla_hours": task.sla_hours,
        "criteria": len(task.acceptance_criteria),
        "cost_usd": str(task.generation_cost_usd),
    }


@tech_lead_app.command("generate-task")
def tech_lead_generate_task() -> None:
    """Gera 1 task via DeepSeek e persiste no Postgres."""
    logger.bind(module="cli.tech_lead").info("tech-lead generate-task")
    result = asyncio.run(_tech_lead_generate())
    if result is None:
        typer.echo("⚠ Nenhum item de backlog disponível (ou DeepSeek falhou)")
        raise typer.Exit(code=1)
    typer.echo(json.dumps(result, indent=2, ensure_ascii=False))


async def _tech_lead_count() -> dict[str, int]:
    from melicrowd.tech_lead.repository import TaskRepository

    factory = get_session_factory()
    async with factory() as session:
        repo = TaskRepository(session)
        counts = await repo.count_by_status()
    await dispose_engine()
    return counts


@tech_lead_app.command("count")
def tech_lead_count() -> None:
    """Mostra contagem de tasks por status."""
    counts = asyncio.run(_tech_lead_count())
    typer.echo(json.dumps(counts, indent=2, ensure_ascii=False))


async def _tech_lead_evaluate(task_id: str) -> dict | None:
    from uuid import UUID as _UUID

    from melicrowd.tech_lead.service import TechLeadService

    factory = get_session_factory()
    async with factory() as session:
        service = TechLeadService(session)
        task = await service.evaluate(_UUID(task_id))
    await dispose_engine()
    if task is None:
        return None
    return {
        "task_id": str(task.task_id),
        "status": task.status.value,
        "checks_passed": sum(1 for r in (task.last_check_results or []) if r.passed),
        "checks_total": len(task.last_check_results or []),
    }


@tech_lead_app.command("evaluate")
def tech_lead_evaluate(task_id: str = typer.Argument(..., help="UUID da task")) -> None:
    """Roda critérios de aceite e atualiza status conforme resultado."""
    result = asyncio.run(_tech_lead_evaluate(task_id))
    if result is None:
        typer.echo(f"⚠ Task {task_id} não encontrada")
        raise typer.Exit(code=1)
    typer.echo(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    app()
