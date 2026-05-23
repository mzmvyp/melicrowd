"""Schemas request/response do router /tasks."""
from __future__ import annotations

from pydantic import BaseModel, Field

from melicrowd.tech_lead.models import Task


class GenerateTaskResponse(BaseModel):
    task: Task
    message: str = "task gerada"


class TaskListResponse(BaseModel):
    total: int
    offset: int
    limit: int
    items: list[Task]
    counts_by_status: dict[str, int] = Field(default_factory=dict)


class EvaluateResponse(BaseModel):
    task: Task
    all_passed: bool
    passed: int
    failed: int
