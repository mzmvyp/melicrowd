"""Demo CLI: roda 1 sessão para uma persona específica e imprime o resumo.

Uso:
    python -m melicrowd.agents.demo --persona-id <UUID>
    python -m melicrowd.agents.demo --random
"""
from __future__ import annotations

import asyncio
import json
from uuid import UUID

import typer
from loguru import logger

from melicrowd.agents.runner import run_session
from melicrowd.db import dispose_engine, get_session_factory
from melicrowd.logging_setup import configure_logging
from melicrowd.personas.repository import PersonaRepository

app = typer.Typer(no_args_is_help=True, help="Roda 1 sessão de demonstração.")


async def _resolve_persona(persona_id: UUID | None) -> object | None:
    factory = get_session_factory()
    async with factory() as session:
        repo = PersonaRepository(session)
        if persona_id:
            return await repo.get_by_id(persona_id)
        sample = await repo.get_random(1)
        return sample[0] if sample else None


async def _run(persona_id: UUID | None) -> None:
    persona = await _resolve_persona(persona_id)
    if persona is None:
        typer.echo("nenhuma persona encontrada — rode `make seed-personas COUNT=200` antes.")
        await dispose_engine()
        raise typer.Exit(code=2)

    final = await run_session(persona)  # type: ignore[arg-type]

    summary = {
        "session_id": str(final.session_id),
        "persona": {
            "name": final.persona.name,
            "income_class": final.persona.income_class.value,
            "location": f"{final.persona.location_city}/{final.persona.location_state}",
        },
        "outcome": final.outcome.value if final.outcome else "unknown",
        "intent": final.session_intent.value if final.session_intent else None,
        "qwen_calls": final.qwen_calls_count,
        "melisim_calls": final.melisim_calls_count,
        "products_viewed": len(final.viewed_products),
        "cart_items": len(final.cart),
        "purchase_total_brl": final.purchase_total_brl,
        "decision_trace_count": len(final.decision_trace),
    }
    typer.echo(json.dumps(summary, indent=2, ensure_ascii=False))
    await dispose_engine()


@app.command()
def main(
    persona_id: UUID | None = typer.Option(None, "--persona-id"),
    random_pick: bool = typer.Option(False, "--random"),
) -> None:
    """Roda 1 sessão. Se ``--random``, sorteia uma persona; senão usa o ID dado."""
    configure_logging()
    if not persona_id and not random_pick:
        typer.echo("informe --persona-id <UUID> ou --random")
        raise typer.Exit(code=2)
    asyncio.run(_run(persona_id))


if __name__ == "__main__":
    app()
