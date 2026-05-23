"""WebSocket /ws/agents — broadcast em tempo real do estado do simulador.

Cada cliente conectado recebe a cada ``BROADCAST_INTERVAL_SECONDS`` o
snapshot completo:
    {
      "agents": [...],
      "events": [...],
      "kpis": {...}
    }

Serve como source-of-truth ÚNICO do frontend Live Floor — sem dados
simulados, só estado real do orchestrator.
"""
from __future__ import annotations

import asyncio
import json
from typing import Final

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from melicrowd.observability.live_tracker import get_tracker

router = APIRouter()
LOGGER = logger.bind(module="api.routers.websocket")

BROADCAST_INTERVAL_SECONDS: Final[float] = 0.2


@router.websocket("/ws/agents")
async def agents_stream(websocket: WebSocket) -> None:
    """Stream de estado dos agentes em tempo real.

    Cliente conecta, recebe snapshot inicial imediatamente, depois um
    snapshot a cada 200ms enquanto a conexão estiver aberta.
    """
    await websocket.accept()
    tracker = get_tracker()
    LOGGER.info("ws client connected", extra={"client": websocket.client and websocket.client.host})

    try:
        # Snapshot imediato (não esperar o primeiro tick).
        first = await tracker.snapshot()
        await websocket.send_text(json.dumps({"type": "snapshot", "data": first}))

        while True:
            await asyncio.sleep(BROADCAST_INTERVAL_SECONDS)
            payload = await tracker.snapshot()
            try:
                await websocket.send_text(json.dumps({"type": "snapshot", "data": payload}))
            except WebSocketDisconnect:
                break
            except Exception as exc:  # noqa: BLE001
                LOGGER.debug("ws send failed (client gone)", extra={"error": str(exc)[:120]})
                break
    except WebSocketDisconnect:
        pass
    finally:
        LOGGER.info("ws client disconnected")
