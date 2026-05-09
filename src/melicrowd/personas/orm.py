"""ORM SQLAlchemy 2.x para a camada Persona.

Espelha a tabela ``melicrowd.personas`` da migration ``0001_initial_schema``.
Usado pelo repository async com asyncpg.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func

SCHEMA = "melicrowd"


class Base(DeclarativeBase):
    """Base declarativa para todos os ORM models do MeliCrowd."""

    metadata = None  # type: ignore[assignment]


# Configuração explícita do schema do MetaData.
from sqlalchemy import MetaData  # noqa: E402

Base.metadata = MetaData(schema=SCHEMA)


class PersonaORM(Base):
    """Persona persistida em ``melicrowd.personas``."""

    __tablename__ = "personas"
    __table_args__ = (
        CheckConstraint("age BETWEEN 18 AND 85", name="ck_persona_age_range"),
        CheckConstraint("gender IN ('F', 'M', 'NB')", name="ck_persona_gender"),
        CheckConstraint("income_class IN ('A', 'B', 'C', 'D')", name="ck_persona_income_class"),
        CheckConstraint("price_sensitivity BETWEEN 0.0 AND 1.0", name="ck_persona_price_sensitivity"),
        CheckConstraint("abandonment_likelihood BETWEEN 0.0 AND 1.0", name="ck_persona_abandonment"),
        {"schema": SCHEMA},
    )

    persona_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    gender: Mapped[str] = mapped_column(String(8), nullable=False)
    location_state: Mapped[str] = mapped_column(String(2), nullable=False)
    location_city: Mapped[str] = mapped_column(String(120), nullable=False)
    income_class: Mapped[str] = mapped_column(String(1), nullable=False)
    occupation: Mapped[str] = mapped_column(String(120), nullable=False)
    interests: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    purchase_drivers: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    price_sensitivity: Mapped[float] = mapped_column(Float, nullable=False)
    brand_loyalty: Mapped[float] = mapped_column(Float, nullable=False)
    risk_tolerance: Mapped[float] = mapped_column(Float, nullable=False)
    digital_savviness: Mapped[float] = mapped_column(Float, nullable=False)
    avg_session_duration_min: Mapped[int] = mapped_column(Integer, nullable=False)
    weekly_visit_frequency: Mapped[int] = mapped_column(Integer, nullable=False)
    preferred_categories: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    abandonment_likelihood: Mapped[float] = mapped_column(Float, nullable=False)
    review_likelihood: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
