"""Schemas das rotas de inspeção de sessão."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SessionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: UUID
    persona_id: UUID
    melisim_user_id: str | None
    session_intent: str | None
    outcome: str
    purchase_total_brl: Decimal
    started_at: datetime
    ended_at: datetime
    duration_seconds: int
    qwen_calls_count: int
    melisim_calls_count: int


class DecisionStep(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    decision_id: UUID
    node: str
    latency_ms: int
    fallback_used: bool
    error: str | None
    response_parsed: dict[str, Any] | None
    timestamp: datetime


class SessionReplay(BaseModel):
    """Replay completo: summary + steps ordenados."""

    summary: SessionSummary
    steps: list[DecisionStep]


class AgentSnapshot(BaseModel):
    """Snapshot leve de um agente ativo (para /agents)."""

    worker_name: str
    running: bool


class AgentList(BaseModel):
    active_agents: int
    target_agents: int
    workers: list[AgentSnapshot]
