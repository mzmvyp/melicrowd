"""Repository async para tech_lead_tasks."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Final
from uuid import UUID

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from melicrowd.tech_lead.models import (
    AcceptanceCheck,
    CheckResult,
    Task,
    TaskCategory,
    TaskPriority,
    TaskStatus,
)
from melicrowd.tech_lead.orm import TaskORM

LOGGER: Final = logger.bind(module="tech_lead.repository")


class TaskRepository:
    """CRUD async para tarefas do Tech Lead."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, task: Task) -> None:
        row = TaskORM(
            task_id=task.task_id,
            title=task.title,
            description=task.description,
            category=task.category.value if hasattr(task.category, "value") else task.category,
            priority=task.priority.value if hasattr(task.priority, "value") else task.priority,
            status=task.status.value if hasattr(task.status, "value") else task.status,
            sla_hours=task.sla_hours,
            acceptance_criteria=[c.model_dump(mode="json") for c in task.acceptance_criteria],
            feedback_history=task.feedback_history,
            tags=task.tags,
            llm_model=task.llm_model,
            generation_cost_usd=task.generation_cost_usd,
        )
        self.session.add(row)
        await self.session.flush()

    async def get(self, task_id: UUID) -> Task | None:
        stmt = select(TaskORM).where(TaskORM.task_id == task_id)
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        return _to_pydantic(row) if row else None

    async def list_paginated(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        status: TaskStatus | None = None,
    ) -> list[Task]:
        stmt = select(TaskORM).order_by(TaskORM.priority.desc(), TaskORM.generated_at.desc())
        if status is not None:
            stmt = stmt.where(TaskORM.status == status.value)
        stmt = stmt.offset(offset).limit(limit)
        rows = (await self.session.execute(stmt)).scalars().all()
        return [_to_pydantic(r) for r in rows]

    async def count_by_status(self) -> dict[str, int]:
        stmt = select(TaskORM.status, func.count()).group_by(TaskORM.status)
        return {status: int(n) for (status, n) in (await self.session.execute(stmt)).all()}

    async def transition(self, task_id: UUID, new_status: TaskStatus) -> Task | None:
        stmt = select(TaskORM).where(TaskORM.task_id == task_id)
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        row.status = new_status.value
        now = datetime.now(timezone.utc)
        if new_status == TaskStatus.IN_PROGRESS and row.started_at is None:
            row.started_at = now
        elif new_status == TaskStatus.REVIEW:
            row.submitted_at = now
        elif new_status == TaskStatus.DONE:
            row.completed_at = now
        await self.session.flush()
        return _to_pydantic(row)

    async def save_check_results(
        self,
        task_id: UUID,
        results: list[CheckResult],
        cost_usd: Decimal = Decimal("0"),
        feedback: str | None = None,
    ) -> None:
        stmt = select(TaskORM).where(TaskORM.task_id == task_id)
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return
        row.last_check_results = [r.model_dump(mode="json") for r in results]
        row.last_evaluated_at = datetime.now(timezone.utc)
        row.evaluation_cost_usd = (row.evaluation_cost_usd or Decimal("0")) + cost_usd
        if feedback:
            history = list(row.feedback_history or [])
            history.append({"ts": row.last_evaluated_at.isoformat(), "feedback": feedback})
            row.feedback_history = history
        await self.session.flush()


def _to_pydantic(row: TaskORM) -> Task:
    return Task(
        task_id=row.task_id,
        title=row.title,
        description=row.description,
        category=TaskCategory(row.category),
        priority=TaskPriority(row.priority),
        status=TaskStatus(row.status),
        sla_hours=row.sla_hours,
        acceptance_criteria=[AcceptanceCheck.model_validate(c) for c in (row.acceptance_criteria or [])],
        last_check_results=(
            [CheckResult.model_validate(r) for r in row.last_check_results]
            if row.last_check_results
            else None
        ),
        feedback_history=list(row.feedback_history or []),
        tags=list(row.tags or []),
        llm_model=row.llm_model,
        generation_cost_usd=row.generation_cost_usd or Decimal("0"),
        evaluation_cost_usd=row.evaluation_cost_usd or Decimal("0"),
        generated_at=row.generated_at,
        started_at=row.started_at,
        submitted_at=row.submitted_at,
        completed_at=row.completed_at,
        last_evaluated_at=row.last_evaluated_at,
    )
