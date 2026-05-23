"""ORM SQLAlchemy para tech_lead_tasks."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from melicrowd.personas.orm import SCHEMA, Base


class TaskORM(Base):
    """Task persistida em ``melicrowd.tech_lead_tasks``."""

    __tablename__ = "tech_lead_tasks"
    __table_args__ = (
        CheckConstraint(
            "category IN ('feature', 'bugfix', 'refactor', 'security', 'observability', 'devx', 'docs')",
            name="ck_task_category",
        ),
        CheckConstraint("priority IN ('low', 'medium', 'high', 'critical')", name="ck_task_priority"),
        CheckConstraint(
            "status IN ('backlog', 'in_progress', 'review', 'done', 'blocked', 'rejected')",
            name="ck_task_status",
        ),
        {"schema": SCHEMA},
    )

    task_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="backlog")
    sla_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    acceptance_criteria: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    last_check_results: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    feedback_history: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    tags: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    llm_model: Mapped[str | None] = mapped_column(String(60), nullable=True)
    generation_cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False, default=Decimal("0"))
    evaluation_cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False, default=Decimal("0"))
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
