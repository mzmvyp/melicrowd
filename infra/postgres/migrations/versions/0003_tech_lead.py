"""tech_lead — tasks geradas e avaliadas pelo Tech Lead Agent.

Revision ID: 0003_tech_lead
Revises: 0002_sellers
Create Date: 2026-05-13 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_tech_lead"
down_revision: str | Sequence[str] | None = "0002_sellers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "melicrowd"


def upgrade() -> None:
    """Cria a tabela ``tech_lead_tasks``.

    O Tech Lead Agent (Deepseek-V4-pro) gera tarefas com critérios de aceite
    automatizáveis. Willian implementa, o agente avalia rodando os critérios
    (HTTP/DB/metric/git/test) e fecha quando 100% passam.
    """
    op.create_table(
        "tech_lead_tasks",
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("category", sa.String(40), nullable=False),  # feature|bugfix|refactor|security|observability
        sa.Column("priority", sa.String(10), nullable=False, server_default="medium"),  # low|medium|high|critical
        sa.Column("status", sa.String(20), nullable=False, server_default="backlog"),  # backlog|in_progress|review|done|blocked|rejected
        sa.Column("sla_hours", sa.Integer, nullable=False, server_default="24"),
        sa.Column("acceptance_criteria", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("last_check_results", postgresql.JSONB, nullable=True),
        sa.Column("feedback_history", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("tags", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("llm_model", sa.String(60), nullable=True),
        sa.Column("generation_cost_usd", sa.Numeric(10, 6), nullable=False, server_default="0"),
        sa.Column("evaluation_cost_usd", sa.Numeric(10, 6), nullable=False, server_default="0"),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "category IN ('feature', 'bugfix', 'refactor', 'security', 'observability', 'devx', 'docs')",
            name="ck_task_category",
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'medium', 'high', 'critical')",
            name="ck_task_priority",
        ),
        sa.CheckConstraint(
            "status IN ('backlog', 'in_progress', 'review', 'done', 'blocked', 'rejected')",
            name="ck_task_status",
        ),
        schema=SCHEMA,
    )
    op.create_index("ix_tasks_status", "tech_lead_tasks", ["status"], schema=SCHEMA)
    op.create_index("ix_tasks_priority", "tech_lead_tasks", ["priority"], schema=SCHEMA)
    op.create_index("ix_tasks_generated_at", "tech_lead_tasks", ["generated_at"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_table("tech_lead_tasks", schema=SCHEMA)
