"""Gerador de tasks via DeepSeek-V4-pro.

Picka 1 item do ``backlog.json`` que ainda não virou task done/in_progress,
chama DeepSeek com o ``system_prompt`` da persona Rafael, valida com Pydantic
e retorna ``Task`` pronta pra persistir.
"""
from __future__ import annotations

import json
import random
from decimal import Decimal
from importlib import resources
from typing import Any, Final

from loguru import logger
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from melicrowd.tech_lead.deepseek_client import generate_json
from melicrowd.tech_lead.models import GeneratedTaskResponse, Task, TaskCategory, TaskPriority, TaskStatus
from melicrowd.tech_lead.orm import TaskORM
from melicrowd.tech_lead.persona import SYSTEM_PROMPT
from melicrowd.tech_lead.prompts import GENERATE_TASK

LOGGER: Final = logger.bind(module="tech_lead.generator")


def load_backlog() -> list[dict[str, Any]]:
    """Carrega o backlog.json embarcado no package."""
    raw = (resources.files("melicrowd.tech_lead") / "backlog.json").read_text(encoding="utf-8")
    data = json.loads(raw)
    return data.get("items", [])


async def _used_backlog_ids(db: AsyncSession) -> set[str]:
    """Retorna IDs de backlog já cobertos por qualquer task viva (inclusive backlog).

    Sem ``backlog`` aqui, gerar 2x seguidas pega o mesmo item critical do JSON.
    Só ``rejected`` libera o slot pra regerar.
    """
    stmt = select(TaskORM.tags).where(
        TaskORM.status.in_(("backlog", "in_progress", "review", "done", "blocked"))
    )
    result = await db.execute(stmt)
    used: set[str] = set()
    for (tags,) in result.all():
        if tags:
            for t in tags:
                if isinstance(t, str) and t.startswith("backlog:"):
                    used.add(t.split(":", 1)[1])
    return used


async def pick_backlog_item(db: AsyncSession) -> dict[str, Any] | None:
    """Escolhe um item do backlog que ainda não virou task ativa.

    Filtra por ``target='melicrowd'`` — o evaluator só consegue checar
    critérios contra o próprio MeliCrowd (http://api:8101, schema ``melicrowd``,
    repo local). Itens com ``target='melisim'`` pertencem ao sistema vizinho
    e ficariam com critérios pra sempre vermelhos (descasamento de escopo
    que já gerou tasks fantasma no histórico — ver task stock-update-idempotency).
    """
    items = load_backlog()
    used = await _used_backlog_ids(db)
    available = [
        it for it in items
        if it["id"] not in used and it.get("target", "melicrowd") == "melicrowd"
    ]
    if not available:
        LOGGER.info("backlog exhausted — todos os itens melicrowd já têm task ativa/done")
        return None
    # Ordena por prioridade (critical > high > medium > low) + shuffle dentro do nível.
    priority_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    available.sort(key=lambda it: priority_rank.get(it.get("suggested_priority", "medium"), 2))
    top_priority = available[0].get("suggested_priority", "medium")
    same_priority = [it for it in available if it.get("suggested_priority") == top_priority]
    return random.choice(same_priority)


def _fallback_task(item: dict[str, Any]) -> tuple[GeneratedTaskResponse, Decimal]:
    """Task default se DeepSeek falhar — sem critérios mensuráveis ricos."""
    return (
        GeneratedTaskResponse(
            title=item["headline"][:200],
            description=(
                f"## Contexto\n{item.get('rationale', '')}\n\n"
                f"## Implementação esperada\n"
                f"{', '.join(item.get('hints', []))}\n\n"
                "## Notas técnicas\n"
                "Fallback procedural — DeepSeek indisponível. Tech lead vai validar manualmente."
            ),
            category=item.get("suggested_category", "feature"),  # type: ignore[arg-type]
            priority=item.get("suggested_priority", "medium"),  # type: ignore[arg-type]
            sla_hours=24,
            acceptance_criteria=[
                {  # type: ignore[list-item]
                    "kind": "git",
                    "description": f"Implementação relacionada ao backlog item {item['id']}",
                    "git_pattern": item["id"].replace("-", "[-_]"),
                }
            ],
            tags=[f"backlog:{item['id']}", "fallback"],
        ),
        Decimal("0"),
    )


async def generate_task_from_backlog(db: AsyncSession) -> Task | None:
    """Pipeline completo: pick backlog → DeepSeek → Pydantic → Task.

    Returns:
        ``Task`` pronta pra persistir, ou ``None`` se backlog esgotado.
    """
    item = await pick_backlog_item(db)
    if item is None:
        return None

    user_prompt = GENERATE_TASK.format(
        item_id=item["id"],
        headline=item["headline"],
        rationale=item.get("rationale", ""),
        suggested_category=item.get("suggested_category", "feature"),
        suggested_priority=item.get("suggested_priority", "medium"),
        hints=", ".join(item.get("hints", [])),
    )

    try:
        response = await generate_json(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            timeout=180.0,
            temperature=0.4,
            max_tokens=6000,
        )
        if response.parsed_json is None:
            LOGGER.warning("deepseek returned no JSON; using fallback")
            generated, cost = _fallback_task(item)
            model = response.model
            actual_cost = response.cost_usd
        else:
            generated = GeneratedTaskResponse.model_validate(response.parsed_json)
            model = response.model
            actual_cost = response.cost_usd
    except ValidationError as exc:
        LOGGER.warning(f"deepseek output failed pydantic validation; fallback. err={str(exc)[:300]}")
        generated, _ = _fallback_task(item)
        model = "fallback"
        actual_cost = Decimal("0")
    except Exception as exc:  # noqa: BLE001  (rede / chave / quota)
        LOGGER.warning(f"deepseek call failed; fallback. err_type={type(exc).__name__} err={str(exc)[:300]}")
        generated, _ = _fallback_task(item)
        model = "fallback"
        actual_cost = Decimal("0")

    # Garante tag backlog:<id> pra rastrear cobertura.
    backlog_tag = f"backlog:{item['id']}"
    if backlog_tag not in generated.tags:
        generated.tags.append(backlog_tag)

    task = Task(
        title=generated.title,
        description=generated.description,
        category=TaskCategory(generated.category),
        priority=TaskPriority(generated.priority),
        status=TaskStatus.BACKLOG,
        sla_hours=generated.sla_hours,
        acceptance_criteria=generated.acceptance_criteria,
        tags=generated.tags,
        llm_model=model,
        generation_cost_usd=actual_cost,
    )
    LOGGER.info(
        "task generated",
        extra={
            "task_id": str(task.task_id),
            "title": task.title,
            "category": str(task.category),
            "criteria": len(task.acceptance_criteria),
            "cost_usd": float(actual_cost),
        },
    )
    return task
