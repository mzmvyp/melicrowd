"""FastAPI app — control plane do MeliCrowd."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.responses import Response

from melicrowd import __version__
from melicrowd.api.routers import control as control_router
from melicrowd.api.routers import inspect as inspect_router
from melicrowd.api.routers import personas as personas_router
from melicrowd.api.routers import sellers as sellers_router
from melicrowd.api.routers import tasks as tasks_router
from melicrowd.api.routers import websocket as websocket_router
from melicrowd.api.state import get_app_state
from melicrowd.config import settings
from melicrowd.db import dispose_engine
from melicrowd.execution.kafka_publisher import get_publisher
from melicrowd.llm.qwen_client import close_client as close_qwen_client
from melicrowd.logging_setup import configure_logging

limiter = Limiter(key_func=get_remote_address, default_limits=[f"{settings.api_rate_limit_per_minute}/minute"])


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Bootstrap/teardown — pool é criado on-demand via /start."""
    configure_logging()
    logger.bind(module="api.main").info(
        "api startup",
        extra={"version": __version__, "port": settings.api_port},
    )
    yield
    state = get_app_state()
    if state.pool is not None:
        await state.pool.shutdown(timeout=30.0)
    if state.seller_pool is not None:
        await state.seller_pool.shutdown(timeout=30.0)
    await get_publisher().stop()
    await close_qwen_client()
    await dispose_engine()
    logger.bind(module="api.main").info("api shutdown")


app = FastAPI(
    title="MeliCrowd Control API",
    version=__version__,
    description=(
        "Control plane do simulador multi-agente. Rotas:\n"
        "- `/start`, `/stop`, `/scale` — controle do pool\n"
        "- `/agents`, `/sessions/{id}`, `/sessions/{id}/replay` — inspeção\n"
        "- `/personas/generate`, `/personas` — geração de personas\n"
        "- `/ws/agents` — WebSocket com snapshot ao vivo (consumido pelo Live Floor)\n"
        "- `/metrics` — Prometheus"
    ),
    lifespan=_lifespan,
)

# CORS — Live Floor (porta 8503) e Streamlit (8502) consomem esta API.
# Em produção, restringir origins. Aqui aceita o range de portas locais usado.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8502",
        "http://localhost:8503",
        "http://127.0.0.1:8502",
        "http://127.0.0.1:8503",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

app.include_router(control_router.router)
app.include_router(inspect_router.router)
app.include_router(personas_router.router)
app.include_router(sellers_router.router)
app.include_router(tasks_router.router)
app.include_router(websocket_router.router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/status", tags=["health"])
async def status_endpoint() -> dict[str, object]:
    state = get_app_state()
    pool_running = state.is_running()
    return {
        "version": __version__,
        "config": {
            "qwen_model": settings.qwen_model,
            "qwen_max_concurrent": settings.qwen_max_concurrent,
            "default_agent_count": settings.default_agent_count,
            "melisim_gateway_url": settings.melisim_gateway_url,
            "live_floor_fast_node_delay_seconds": settings.live_floor_fast_node_delay_seconds,
        },
        "pool": {
            "running": pool_running,
            "active_agents": state.pool.active_agents if state.pool else 0,
            "target_agents": state.pool.target_size if state.pool else 0,
        },
    }


@app.get("/metrics", tags=["observability"])
async def metrics(_request: Request) -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
