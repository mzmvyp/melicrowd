"""Modelos Pydantic da camada Tech Lead."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class TaskCategory(str, Enum):
    FEATURE = "feature"
    BUGFIX = "bugfix"
    REFACTOR = "refactor"
    SECURITY = "security"
    OBSERVABILITY = "observability"
    DEVX = "devx"
    DOCS = "docs"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskStatus(str, Enum):
    BACKLOG = "backlog"          # tech lead gerou, dev ainda não começou
    IN_PROGRESS = "in_progress"  # dev clicou "start", SLA timer roda
    REVIEW = "review"            # dev clicou "submit", auto-eval ativo
    DONE = "done"                # auto-eval passou 100%
    BLOCKED = "blocked"          # auto-eval falhou, tech lead deu feedback
    REJECTED = "rejected"        # tech lead recusou (rara — má spec)


class CheckKind(str, Enum):
    """Tipos de check automatizáveis no acceptance_criteria.

    Cada kind tem um conjunto de campos esperados — ver ``AcceptanceCheck``.
    """

    HTTP = "http"          # GET/POST/PATCH em URL com status esperado
    DB = "db"              # SQL query retorna >= 1 linha (ou valor esperado)
    METRIC = "metric"      # contador Prometheus aumenta / atinge mínimo
    GIT = "git"            # commit message bate regex ou arquivo existe
    TEST = "test"          # pytest path passa
    ENDPOINT_EXISTS = "endpoint_exists"  # API tem rota registrada


class AcceptanceCheck(BaseModel):
    """Um check executável pelo evaluator."""

    kind: CheckKind
    description: str = Field(min_length=4, max_length=200)
    # http
    method: str | None = None
    url: str | None = None
    expected_status: int | None = None
    response_contains: str | None = None
    request_body: dict | None = None
    # db
    query: str | None = None  # PostgreSQL contra melicrowd db
    expect_min_rows: int | None = None
    expect_value: str | None = None
    # metric
    metric_name: str | None = None
    metric_min_value: float | None = None
    # git
    git_pattern: str | None = None
    git_file_exists: str | None = None
    # test
    pytest_path: str | None = None
    # endpoint_exists
    openapi_path: str | None = None
    openapi_method: str | None = None


class CheckResult(BaseModel):
    """Resultado de execução de um check."""

    check: AcceptanceCheck
    passed: bool
    detail: str = ""
    ran_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Task(BaseModel):
    """Task gerada pelo Tech Lead Agent."""

    model_config = ConfigDict(use_enum_values=True)

    task_id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=4, max_length=200)
    description: str = Field(min_length=20)
    category: TaskCategory
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.BACKLOG
    sla_hours: int = Field(default=24, ge=1, le=720)
    acceptance_criteria: list[AcceptanceCheck] = Field(default_factory=list, min_length=1)
    last_check_results: list[CheckResult] | None = None
    feedback_history: list[dict] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    llm_model: str | None = None
    generation_cost_usd: Decimal = Decimal("0")
    evaluation_cost_usd: Decimal = Decimal("0")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    submitted_at: datetime | None = None
    completed_at: datetime | None = None
    last_evaluated_at: datetime | None = None


class GeneratedTaskResponse(BaseModel):
    """Saída do Deepseek na geração de tarefa.

    Tudo é validado por Pydantic antes de virar Task. Se Deepseek retornar
    JSON ruim, fallback procedural cria task simples.
    """

    title: str = Field(min_length=4, max_length=200)
    description: str = Field(min_length=20)
    category: Literal["feature", "bugfix", "refactor", "security", "observability", "devx", "docs"]
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    sla_hours: int = Field(default=24, ge=1, le=168)
    acceptance_criteria: list[AcceptanceCheck] = Field(min_length=1, max_length=10)
    tags: list[str] = Field(default_factory=list, max_length=8)
