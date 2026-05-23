"""Router /sellers — geração de personas + controle do pool de vendedores."""
from __future__ import annotations

import time
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from melicrowd.api.deps import get_session
from melicrowd.api.schemas.sellers import (
    SeedRequest,
    SeedResponse,
    SellerListResponse,
    SellerPoolScaleResponse,
    SellerPoolStartResponse,
    SellerPoolStatus,
    SellerPoolStopResponse,
)
from melicrowd.api.state import get_app_state
from melicrowd.orchestrator.seller_pool import SellerPool
from melicrowd.sellers.models import SellerPersona
from melicrowd.sellers.service import SellerService

router = APIRouter(prefix="/sellers", tags=["sellers"])
LOGGER = logger.bind(module="api.routers.sellers")


# -----------------------------------------------------------------------------
# Personas
# -----------------------------------------------------------------------------


@router.post(
    "/seed-synthetic",
    response_model=SeedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def seed_synthetic(
    payload: SeedRequest,
    db: AsyncSession = Depends(get_session),
) -> SeedResponse:
    """Cria N personas seller sintéticas (sem Qwen) — útil pra dev rápido."""
    service = SellerService(db)
    personas = await service.seed_synthetic(payload.count)
    return SeedResponse(
        requested=payload.count,
        delivered=len(personas),
        sample=personas[:5],
    )


@router.get("", response_model=SellerListResponse)
async def list_sellers(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
) -> SellerListResponse:
    """Lista paginada de personas seller."""
    service = SellerService(db)
    items = await service.list(offset=offset, limit=limit)
    total = await service.count()
    return SellerListResponse(total=total, offset=offset, limit=limit, items=items)


@router.get("/{seller_persona_id}", response_model=SellerPersona)
async def get_seller(
    seller_persona_id: UUID,
    db: AsyncSession = Depends(get_session),
) -> SellerPersona:
    service = SellerService(db)
    persona = await service.get(seller_persona_id)
    if persona is None:
        raise HTTPException(status_code=404, detail=f"seller {seller_persona_id} não encontrado")
    return persona


# -----------------------------------------------------------------------------
# Pool control
# -----------------------------------------------------------------------------


@router.post(
    "/start",
    response_model=SellerPoolStartResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_pool(
    workers: int = Query(default=5, ge=1, le=50),
) -> SellerPoolStartResponse:
    """Inicia o pool de vendedores."""
    state = get_app_state()
    async with state.seller_pool_lock:
        if state.seller_pool is not None and state.seller_pool.is_running:
            raise HTTPException(
                status_code=409, detail="seller pool já está rodando — use /sellers/scale"
            )
        state.seller_pool = SellerPool(target_size=workers)
        await state.seller_pool.start()
        LOGGER.info("seller pool started via API", extra={"workers": workers})
    return SellerPoolStartResponse(
        target_workers=state.seller_pool.target_size,
        active_workers=state.seller_pool.active_workers,
        running=state.seller_pool.is_running,
    )


@router.post("/stop", response_model=SellerPoolStopResponse)
async def stop_pool(
    graceful: bool = Query(default=True),
    timeout_seconds: float = Query(default=30.0, ge=0.0, le=600.0),
) -> SellerPoolStopResponse:
    state = get_app_state()
    async with state.seller_pool_lock:
        if state.seller_pool is None:
            raise HTTPException(status_code=404, detail="seller pool não foi iniciado")
        started = time.monotonic()
        timeout = timeout_seconds if graceful else 0.0
        await state.seller_pool.shutdown(timeout=timeout)
        elapsed = time.monotonic() - started
        active = state.seller_pool.active_workers
        state.seller_pool = None
    return SellerPoolStopResponse(drained_in_seconds=round(elapsed, 2), active_workers=active)


@router.post("/scale", response_model=SellerPoolScaleResponse)
async def scale_pool(
    workers: int = Query(..., ge=0, le=50),
) -> SellerPoolScaleResponse:
    state = get_app_state()
    async with state.seller_pool_lock:
        if state.seller_pool is None:
            raise HTTPException(
                status_code=404, detail="seller pool não foi iniciado — chame /sellers/start"
            )
        previous = state.seller_pool.target_size
        active = await state.seller_pool.resize(workers)
    return SellerPoolScaleResponse(previous_size=previous, new_size=workers, active_workers=active)


@router.get("/pool/status", response_model=SellerPoolStatus, tags=["health"])
async def pool_status() -> SellerPoolStatus:
    state = get_app_state()
    if state.seller_pool is None:
        return SellerPoolStatus(running=False, target_workers=0, active_workers=0)
    return SellerPoolStatus(
        running=state.seller_pool.is_running,
        target_workers=state.seller_pool.target_size,
        active_workers=state.seller_pool.active_workers,
    )
