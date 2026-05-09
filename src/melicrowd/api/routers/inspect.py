"""Router de inspeção: /agents, /sessions/{id}, /sessions/{id}/replay."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from melicrowd.api.deps import get_session
from melicrowd.api.schemas.sessions import (
    AgentList,
    AgentSnapshot,
    DecisionStep,
    SessionReplay,
    SessionSummary,
)
from melicrowd.api.state import get_app_state
from melicrowd.sessions.repository import SessionRepository

router = APIRouter(tags=["inspect"])


@router.get("/agents", response_model=AgentList)
async def list_agents() -> AgentList:
    """Lista os workers ativos do pool."""
    state = get_app_state()
    if state.pool is None:
        return AgentList(active_agents=0, target_agents=0, workers=[])
    workers = [
        AgentSnapshot(worker_name=task.get_name(), running=not task.done())
        for task in state.pool._tasks  # noqa: SLF001  (interno, mas ok pra inspeção)
    ]
    return AgentList(
        active_agents=state.pool.active_agents,
        target_agents=state.pool.target_size,
        workers=workers,
    )


@router.get("/sessions", response_model=list[SessionSummary])
async def list_sessions(
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_session),
) -> list[SessionSummary]:
    """Lista as últimas N sessões finalizadas."""
    repo = SessionRepository(db)
    rows = await repo.list_recent(limit=limit)
    return [SessionSummary.model_validate(row) for row in rows]


@router.get("/sessions/{session_id}", response_model=SessionSummary)
async def get_session_detail(
    session_id: UUID,
    db: AsyncSession = Depends(get_session),
) -> SessionSummary:
    repo = SessionRepository(db)
    row = await repo.get(session_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"session {session_id} não encontrada")
    return SessionSummary.model_validate(row)


@router.get("/sessions/{session_id}/replay", response_model=SessionReplay)
async def get_session_replay(
    session_id: UUID,
    db: AsyncSession = Depends(get_session),
) -> SessionReplay:
    """Replay step-by-step: summary + decisões ordenadas."""
    repo = SessionRepository(db)
    summary = await repo.get(session_id)
    if summary is None:
        raise HTTPException(status_code=404, detail=f"session {session_id} não encontrada")
    decisions = await repo.list_decisions(session_id)
    return SessionReplay(
        summary=SessionSummary.model_validate(summary),
        steps=[DecisionStep.model_validate(d) for d in decisions],
    )
