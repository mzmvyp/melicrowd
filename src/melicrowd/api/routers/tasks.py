"""Router /tasks — Tech Lead Agent."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from melicrowd.api.deps import get_session
from melicrowd.api.schemas.tasks import EvaluateResponse, GenerateTaskResponse, TaskListResponse
from melicrowd.tech_lead.models import Task, TaskStatus
from melicrowd.tech_lead.service import TechLeadService

router = APIRouter(prefix="/tasks", tags=["tech_lead"])
LOGGER = logger.bind(module="api.routers.tasks")


@router.post("/generate", response_model=GenerateTaskResponse, status_code=status.HTTP_201_CREATED)
async def generate_task(db: AsyncSession = Depends(get_session)) -> GenerateTaskResponse:
    """Tech Lead gera 1 task baseada no próximo item do backlog blueprint."""
    service = TechLeadService(db)
    task = await service.generate_and_persist()
    if task is None:
        raise HTTPException(status_code=409, detail="backlog esgotado — todas as ideias já viraram task ativa/done")
    return GenerateTaskResponse(task=task, message=f"Task '{task.title}' criada")


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status_filter: TaskStatus | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_session),
) -> TaskListResponse:
    service = TechLeadService(db)
    items = await service.repository.list_paginated(offset=offset, limit=limit, status=status_filter)
    counts = await service.repository.count_by_status()
    total = sum(counts.values())
    return TaskListResponse(
        total=total,
        offset=offset,
        limit=limit,
        items=items,
        counts_by_status=counts,
    )


@router.get("/{task_id}", response_model=Task)
async def get_task(task_id: UUID, db: AsyncSession = Depends(get_session)) -> Task:
    service = TechLeadService(db)
    task = await service.repository.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"task {task_id} não encontrada")
    return task


@router.post("/{task_id}/start", response_model=Task)
async def start_task(task_id: UUID, db: AsyncSession = Depends(get_session)) -> Task:
    """Dev clica 'start' — vai pra in_progress, SLA timer roda."""
    service = TechLeadService(db)
    task = await service.repository.transition(task_id, TaskStatus.IN_PROGRESS)
    if task is None:
        raise HTTPException(status_code=404, detail="task não encontrada")
    await db.commit()
    return task


@router.post("/{task_id}/submit", response_model=EvaluateResponse)
async def submit_task(task_id: UUID, db: AsyncSession = Depends(get_session)) -> EvaluateResponse:
    """Dev clica 'submit' — transiciona pra review e dispara evaluation."""
    service = TechLeadService(db)
    await service.repository.transition(task_id, TaskStatus.REVIEW)
    await db.commit()
    task = await service.evaluate(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task não encontrada após avaliação")
    results = task.last_check_results or []
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    return EvaluateResponse(task=task, all_passed=failed == 0 and bool(results), passed=passed, failed=failed)


@router.post("/{task_id}/evaluate", response_model=EvaluateResponse)
async def evaluate_again(task_id: UUID, db: AsyncSession = Depends(get_session)) -> EvaluateResponse:
    """Re-roda os critérios de aceite sem mudar status (debug)."""
    service = TechLeadService(db)
    task = await service.evaluate(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task não encontrada")
    results = task.last_check_results or []
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    return EvaluateResponse(task=task, all_passed=failed == 0 and bool(results), passed=passed, failed=failed)
