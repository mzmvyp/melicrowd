"""sellers — personas e sessões de vendedores.

Revision ID: 0002_sellers
Revises: 0001_initial_schema
Create Date: 2026-05-11 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_sellers"
down_revision: str | Sequence[str] | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "melicrowd"


def upgrade() -> None:
    """Cria tabelas dedicadas pra vendedores (agentes SELLER do Melisim)."""

    # seller_personas — perfis de vendedores (lojas)
    op.create_table(
        "seller_personas",
        sa.Column(
            "seller_persona_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("store_name", sa.String(140), nullable=False),
        sa.Column("owner_name", sa.String(120), nullable=False),
        sa.Column("location_state", sa.String(2), nullable=False),
        sa.Column("location_city", sa.String(120), nullable=False),
        sa.Column("category_focus", postgresql.JSONB, nullable=False),
        sa.Column("price_strategy", sa.String(20), nullable=False),  # aggressive|standard|premium
        sa.Column("restock_aggressiveness", sa.Float, nullable=False),  # 0-1
        sa.Column("expansion_rate", sa.Float, nullable=False),  # 0-1 — chance de criar produto novo
        sa.Column("min_catalog_size", sa.Integer, nullable=False, default=5),
        sa.Column("max_catalog_size", sa.Integer, nullable=False, default=30),
        sa.Column("session_cooldown_min_seconds", sa.Integer, nullable=False, default=300),
        sa.Column("session_cooldown_max_seconds", sa.Integer, nullable=False, default=1800),
        sa.Column("melisim_user_id", sa.String(64), nullable=True),  # cache do ID após primeiro signup
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "price_strategy IN ('aggressive', 'standard', 'premium')",
            name="ck_seller_price_strategy",
        ),
        sa.CheckConstraint(
            "restock_aggressiveness BETWEEN 0.0 AND 1.0",
            name="ck_seller_restock_aggr",
        ),
        sa.CheckConstraint(
            "expansion_rate BETWEEN 0.0 AND 1.0", name="ck_seller_expansion_rate"
        ),
        schema=SCHEMA,
    )
    op.create_index("ix_seller_personas_state", "seller_personas", ["location_state"], schema=SCHEMA)
    op.create_index("ix_seller_personas_strategy", "seller_personas", ["price_strategy"], schema=SCHEMA)

    # seller_sessions — sessões finalizadas de vendedores
    op.create_table(
        "seller_sessions",
        sa.Column("session_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "seller_persona_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.seller_personas.seller_persona_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("melisim_user_id", sa.String(64), nullable=True),
        sa.Column("session_focus", sa.String(20), nullable=True),  # restock|expand|maintenance|promo
        sa.Column("outcome", sa.String(20), nullable=False),  # ok|partial|error
        sa.Column("products_audited", sa.Integer, nullable=False, default=0),
        sa.Column("notifications_handled", sa.Integer, nullable=False, default=0),
        sa.Column("products_created", sa.Integer, nullable=False, default=0),
        sa.Column("products_restocked", sa.Integer, nullable=False, default=0),
        sa.Column("products_suspended", sa.Integer, nullable=False, default=0),
        sa.Column("prices_updated", sa.Integer, nullable=False, default=0),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Integer, nullable=False),
        sa.Column("qwen_calls_count", sa.Integer, nullable=False, default=0),
        sa.Column("melisim_calls_count", sa.Integer, nullable=False, default=0),
        sa.Column("errors_encountered", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("outcome IN ('ok', 'partial', 'error')", name="ck_seller_session_outcome"),
        schema=SCHEMA,
    )
    op.create_index("ix_seller_sessions_persona", "seller_sessions", ["seller_persona_id"], schema=SCHEMA)
    op.create_index("ix_seller_sessions_ended_at", "seller_sessions", ["ended_at"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_table("seller_sessions", schema=SCHEMA)
    op.drop_table("seller_personas", schema=SCHEMA)
