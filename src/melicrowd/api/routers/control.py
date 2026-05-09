"""Router de controle do pool (/start, /stop, /scale)."""
from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, Query, status
from loguru import logger

from melicrowd.api.schemas.control import PoolStatus, ScaleResponse, StartResponse, StopResponse
from melicrowd.api.state import get_app_state
from melicrowd.config import settings
from melicrowd.execution.kafka_publisher import get_publisher
from melicrowd.llm.pool import get_pool as get_qwen_pool
from melicrowd.orchestrator.pool import AgentPool

router = APIRouter(tags=["control"])
LOGGER = logger.bind(module="api.routers.control")


@router.post("/start", response_model=StartResponse, status_code=status.HTTP_201_CREATED)
async def start(
    agents: int = Query(default=settings.default_agent_count, ge=1, le=500),
) -> StartResponse:
    """Inicia o pool com ``agents`` workers."""
    state = get_app_state()
    async with state.pool_lock:
        if state.pool is not None and state.pool.is_running:
            raise HTTPException(status_code=409, detail="pool já está rodando — use /scale")
        publisher = get_publisher()
        await publisher.start()
        state.pool = AgentPool(target_size=agents)
        await state.pool.start()
        LOGGER.info("pool started via API", extra={"agents": agents})
    return StartResponse(
        target_agents=state.pool.target_size,
        active_agents=state.pool.active_agents,
        running=state.pool.is_running,
    )


@router.post("/stop", response_model=StopResponse)
async def stop(
    graceful: bool = Query(default=True),
    timeout_seconds: float = Query(default=30.0, ge=0.0, le=600.0),
) -> StopResponse:
    """Para o pool. ``graceful=true`` espera sessões em vôo terminarem."""
    state = get_app_state()
    async with state.pool_lock:
        if state.pool is None:
            raise HTTPException(status_code=404, detail="pool não foi iniciado")
        started = time.monotonic()
        timeout = timeout_seconds if graceful else 0.0
        await state.pool.shutdown(timeout=timeout)
        elapsed = time.monotonic() - started
        active = state.pool.active_agents
        state.pool = None
    return StopResponse(drained_in_seconds=round(elapsed, 2), active_agents=active)


@router.post("/scale", response_model=ScaleResponse)
async def scale(
    agents: int = Query(..., ge=0, le=500),
) -> ScaleResponse:
    """Redimensiona o pool em runtime."""
    state = get_app_state()
    async with state.pool_lock:
        if state.pool is None:
            raise HTTPException(status_code=404, detail="pool não foi iniciado — chame /start primeiro")
        previous = state.pool.target_size
        active = await state.pool.resize(agents)
    return ScaleResponse(previous_size=previous, new_size=agents, active_agents=active)


@router.get("/pool", response_model=PoolStatus, tags=["health"])
async def pool_status() -> PoolStatus:
    """Snapshot do pool + estatísticas Qwen."""
    state = get_app_state()
    qwen_stats = get_qwen_pool().stats
    if state.pool is None:
        return PoolStatus(
            running=False,
            target_agents=0,
            active_agents=0,
            qwen_in_flight=qwen_stats["in_flight"],
            qwen_waiting=qwen_stats["waiting"],
        )
    return PoolStatus(
        running=state.pool.is_running,
        target_agents=state.pool.target_size,
        active_agents=state.pool.active_agents,
        qwen_in_flight=qwen_stats["in_flight"],
        qwen_waiting=qwen_stats["waiting"],
    )
