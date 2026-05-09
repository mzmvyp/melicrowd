"""Schemas das rotas de controle (start/stop/scale)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class StartResponse(BaseModel):
    target_agents: int
    active_agents: int
    running: bool


class StopResponse(BaseModel):
    drained_in_seconds: float
    active_agents: int


class ScaleResponse(BaseModel):
    previous_size: int
    new_size: int
    active_agents: int


class PoolStatus(BaseModel):
    """Snapshot do pool — usado em /status."""

    running: bool
    target_agents: int
    active_agents: int
    qwen_in_flight: int = Field(default=0)
    qwen_waiting: int = Field(default=0)
