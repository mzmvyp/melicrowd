"""ORM SQLAlchemy 2.x para a camada Seller."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from melicrowd.personas.orm import SCHEMA, Base


class SellerPersonaORM(Base):
    """Persona de vendedor persistida em ``melicrowd.seller_personas``."""

    __tablename__ = "seller_personas"
    __table_args__ = (
        CheckConstraint(
            "price_strategy IN ('aggressive', 'standard', 'premium')",
            name="ck_seller_price_strategy",
        ),
        CheckConstraint(
            "restock_aggressiveness BETWEEN 0.0 AND 1.0",
            name="ck_seller_restock_aggr",
        ),
        CheckConstraint(
            "expansion_rate BETWEEN 0.0 AND 1.0", name="ck_seller_expansion_rate"
        ),
        {"schema": SCHEMA},
    )

    seller_persona_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    store_name: Mapped[str] = mapped_column(String(140), nullable=False)
    owner_name: Mapped[str] = mapped_column(String(120), nullable=False)
    location_state: Mapped[str] = mapped_column(String(2), nullable=False)
    location_city: Mapped[str] = mapped_column(String(120), nullable=False)
    category_focus: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    price_strategy: Mapped[str] = mapped_column(String(20), nullable=False)
    restock_aggressiveness: Mapped[float] = mapped_column(Float, nullable=False)
    expansion_rate: Mapped[float] = mapped_column(Float, nullable=False)
    min_catalog_size: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    max_catalog_size: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    session_cooldown_min_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    session_cooldown_max_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=1800)
    melisim_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SellerSessionORM(Base):
    """Sessão finalizada de vendedor."""

    __tablename__ = "seller_sessions"
    __table_args__ = (
        CheckConstraint("outcome IN ('ok', 'partial', 'error')", name="ck_seller_session_outcome"),
        {"schema": SCHEMA},
    )

    session_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    seller_persona_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    melisim_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    session_focus: Mapped[str | None] = mapped_column(String(20), nullable=True)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    products_audited: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notifications_handled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    products_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    products_restocked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    products_suspended: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prices_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    qwen_calls_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    melisim_calls_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors_encountered: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
