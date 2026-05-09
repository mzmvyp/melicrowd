"""Cliente HTTP utilitário para as páginas Streamlit chamarem a API.

Streamlit roda no mesmo network Docker da api, então usa hostname ``api:8101``.
Para uso fora de Docker, ajuste ``MELICROWD_API_INTERNAL_URL``.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

API_URL = os.environ.get("MELICROWD_API_INTERNAL_URL", "http://api:8101")
TIMEOUT = httpx.Timeout(15.0)


def _safe_get(path: str, **params: Any) -> Any:
    try:
        with httpx.Client(timeout=TIMEOUT, base_url=API_URL) as client:
            response = client.get(path, params=params)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError:
        return None


def _safe_post(path: str, **params: Any) -> Any:
    try:
        with httpx.Client(timeout=TIMEOUT, base_url=API_URL) as client:
            response = client.post(path, params=params)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as exc:
        return {"error": str(exc)}


def get_status() -> dict[str, Any] | None:
    return _safe_get("/status")


def get_pool_status() -> dict[str, Any] | None:
    return _safe_get("/pool")


def get_agents() -> dict[str, Any] | None:
    return _safe_get("/agents")


def get_personas(limit: int = 50, income_class: str | None = None, location_state: str | None = None) -> dict[str, Any] | None:
    params: dict[str, Any] = {"limit": limit}
    if income_class:
        params["income_class"] = income_class
    if location_state:
        params["location_state"] = location_state
    return _safe_get("/personas", **params)


def get_sessions(limit: int = 50) -> Any | None:
    return _safe_get("/sessions", limit=limit)


def get_session_replay(session_id: str) -> dict[str, Any] | None:
    return _safe_get(f"/sessions/{session_id}/replay")


def post_start(agents: int) -> dict[str, Any] | None:
    return _safe_post("/start", agents=agents)


def post_stop(graceful: bool = True) -> dict[str, Any] | None:
    return _safe_post("/stop", graceful=graceful)


def post_scale(agents: int) -> dict[str, Any] | None:
    return _safe_post("/scale", agents=agents)


def post_personas_generate(count: int) -> dict[str, Any] | None:
    return _safe_post("/personas/generate", count=count)
