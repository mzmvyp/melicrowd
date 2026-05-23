"""Service layer pra tech_lead — orquestra generator + evaluator + repo."""
from __future__ import annotations

from typing import Final
from uuid import UUID

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from melicrowd.tech_lead.evaluator import evaluate_task
from melicrowd.tech_lead.generator import generate_task_from_backlog
from melicrowd.tech_lead.models import Task, TaskStatus
from melicrowd.tech_lead.repository import TaskRepository

LOGGER: Final = logger.bind(module="tech_lead.service")


class TechLeadService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = TaskRepository(session)

    async def generate_and_persist(self) -> Task | None:
        """Gera 1 task via DeepSeek e persiste."""
        task = await generate_task_from_backlog(self.session)
        if task is None:
            return None
        await self.repository.create(task)
        await self.session.commit()
        LOGGER.info("task persisted", extra={"task_id": str(task.task_id), "title": task.title})
        return task

    async def evaluate(self, task_id: UUID) -> Task | None:
        """Roda os critérios de aceite e atualiza status conforme resultado."""
        task = await self.repository.get(task_id)
        if task is None:
            return None
        results = await evaluate_task(task.acceptance_criteria, self.session)
        all_passed = all(r.passed for r in results)
        await self.repository.save_check_results(task_id, results)
        if all_passed:
            await self.repository.transition(task_id, TaskStatus.DONE)
            LOGGER.info("task PASSED all checks", extra={"task_id": str(task_id)})
        elif task.status != TaskStatus.BLOCKED:
            # Falhou — só transiciona pra blocked se estava em review (não interrompe in_progress).
            if task.status == TaskStatus.REVIEW:
                await self.repository.transition(task_id, TaskStatus.BLOCKED)
        await self.session.commit()
        return await self.repository.get(task_id)
