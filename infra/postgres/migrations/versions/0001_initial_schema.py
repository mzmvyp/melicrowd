"""initial schema — personas, sessions, decisions, metrics_snapshots.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-06 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SCHEMA = "melicrowd"


def upgrade() -> None:
    """Cria as 4 tabelas-base do MeliCrowd.

    - personas: catálogo de perfis de usuário gerados por Qwen
    - sessions: sessões finalizadas (Redis tem o estado live)
    - decisions: trace de TODA chamada Qwen (auditoria)
    - metrics_snapshots: snapshots periódicos de KPIs para histórico
    """
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

    # ------------------------------------------------------------------
    # personas
    # ------------------------------------------------------------------
    op.create_table(
        "personas",
        sa.Column(
            "persona_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("age", sa.Integer, nullable=False),
        sa.Column("gender", sa.String(8), nullable=False),
        sa.Column("location_state", sa.String(2), nullable=False),
        sa.Column("location_city", sa.String(120), nullable=False),
        sa.Column("income_class", sa.String(1), nullable=False),
        sa.Column("occupation", sa.String(120), nullable=False),
        sa.Column("interests", postgresql.JSONB, nullable=False),
        sa.Column("purchase_drivers", postgresql.JSONB, nullable=False),
        sa.Column("price_sensitivity", sa.Float, nullable=False),
        sa.Column("brand_loyalty", sa.Float, nullable=False),
        sa.Column("risk_tolerance", sa.Float, nullable=False),
        sa.Column("digital_savviness", sa.Float, nullable=False),
        sa.Column("avg_session_duration_min", sa.Integer, nullable=False),
        sa.Column("weekly_visit_frequency", sa.Integer, nullable=False),
        sa.Column("preferred_categories", postgresql.JSONB, nullable=False),
        sa.Column("abandonment_likelihood", sa.Float, nullable=False),
        sa.Column("review_likelihood", sa.Float, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("age BETWEEN 18 AND 85", name="ck_persona_age_range"),
        sa.CheckConstraint("gender IN ('F', 'M', 'NB')", name="ck_persona_gender"),
        sa.CheckConstraint(
            "income_class IN ('A', 'B', 'C', 'D')",
            name="ck_persona_income_class",
        ),
        sa.CheckConstraint(
            "price_sensitivity BETWEEN 0.0 AND 1.0",
            name="ck_persona_price_sensitivity",
        ),
        sa.CheckConstraint(
            "abandonment_likelihood BETWEEN 0.0 AND 1.0",
            name="ck_persona_abandonment",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_personas_income_class", "personas", ["income_class"], schema=SCHEMA
    )
    op.create_index(
        "ix_personas_location_state", "personas", ["location_state"], schema=SCHEMA
    )

    # ------------------------------------------------------------------
    # sessions — sessões finalizadas (estado live mora no Redis)
    # ------------------------------------------------------------------
    op.create_table(
        "sessions",
        sa.Column("session_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "persona_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.personas.persona_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("melisim_user_id", sa.String(64), nullable=True),
        sa.Column("session_intent", sa.String(16), nullable=True),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("purchase_total_brl", sa.Numeric(12, 2), nullable=False, default=0),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Integer, nullable=False),
        sa.Column("qwen_calls_count", sa.Integer, nullable=False, default=0),
        sa.Column("qwen_total_latency_ms", sa.Integer, nullable=False, default=0),
        sa.Column("melisim_calls_count", sa.Integer, nullable=False, default=0),
        sa.Column("errors_encountered", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "outcome IN ('purchased', 'abandoned_cart', 'browsed_only', 'bounced', 'error')",
            name="ck_session_outcome",
        ),
        schema=SCHEMA,
    )
    op.create_index("ix_sessions_persona_id", "sessions", ["persona_id"], schema=SCHEMA)
    op.create_index("ix_sessions_outcome", "sessions", ["outcome"], schema=SCHEMA)
    op.create_index("ix_sessions_ended_at", "sessions", ["ended_at"], schema=SCHEMA)

    # ------------------------------------------------------------------
    # decisions — toda chamada Qwen é registrada aqui (auditoria)
    # ------------------------------------------------------------------
    op.create_table(
        "decisions",
        sa.Column(
            "decision_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.sessions.session_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "persona_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.personas.persona_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("node", sa.String(64), nullable=False),
        sa.Column("prompt", sa.Text, nullable=False),
        sa.Column("response_raw", sa.Text, nullable=True),
        sa.Column("response_parsed", postgresql.JSONB, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=False),
        sa.Column("fallback_used", sa.Boolean, nullable=False, default=False),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        schema=SCHEMA,
    )
    op.create_index("ix_decisions_session_id", "decisions", ["session_id"], schema=SCHEMA)
    op.create_index("ix_decisions_node", "decisions", ["node"], schema=SCHEMA)
    op.create_index("ix_decisions_timestamp", "decisions", ["timestamp"], schema=SCHEMA)

    # ------------------------------------------------------------------
    # metrics_snapshots — snapshots periódicos para histórico (Prometheus tem retenção curta)
    # ------------------------------------------------------------------
    op.create_table(
        "metrics_snapshots",
        sa.Column(
            "snapshot_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("active_agents", sa.Integer, nullable=False),
        sa.Column("sessions_per_minute", sa.Float, nullable=False),
        sa.Column("conversion_rate", sa.Float, nullable=False),
        sa.Column("abandonment_rate", sa.Float, nullable=False),
        sa.Column("avg_session_duration_seconds", sa.Float, nullable=False),
        sa.Column("qwen_p95_latency_ms", sa.Float, nullable=False),
        sa.Column("qwen_in_flight", sa.Integer, nullable=False),
        sa.Column("custom_metrics", postgresql.JSONB, nullable=False, server_default="{}"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_metrics_snapshots_captured_at",
        "metrics_snapshots",
        ["captured_at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    """Reverte criação do schema inicial."""
    op.drop_table("metrics_snapshots", schema=SCHEMA)
    op.drop_table("decisions", schema=SCHEMA)
    op.drop_table("sessions", schema=SCHEMA)
    op.drop_table("personas", schema=SCHEMA)
