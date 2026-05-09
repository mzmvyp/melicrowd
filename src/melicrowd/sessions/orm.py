"""ORM SQLAlchemy 2.x para sessions e decisions."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from melicrowd.personas.orm import SCHEMA, Base


class SessionORM(Base):
    """Sessão finalizada persistida em ``melicrowd.sessions``."""

    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('purchased', 'abandoned_cart', 'browsed_only', 'bounced', 'error')",
            name="ck_session_outcome",
        ),
        {"schema": SCHEMA},
    )

    session_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    persona_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.personas.persona_id", ondelete="RESTRICT"),
        nullable=False,
    )
    melisim_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    session_intent: Mapped[str | None] = mapped_column(String(16), nullable=True)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    purchase_total_brl: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    qwen_calls_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    qwen_total_latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    melisim_calls_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors_encountered: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DecisionORM(Base):
    """Decisão Qwen persistida em ``melicrowd.decisions`` (auditoria)."""

    __tablename__ = "decisions"
    __table_args__ = ({"schema": SCHEMA},)

    decision_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    persona_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.personas.persona_id", ondelete="RESTRICT"),
        nullable=False,
    )
    node: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    response_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_parsed: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    fallback_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
