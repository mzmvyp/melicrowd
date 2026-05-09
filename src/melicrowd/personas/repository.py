"""Repository async para a camada Persona.

CRUD mínimo necessário para o simulador:
- ``create_batch`` — insere N personas em uma transação.
- ``get_by_id`` — recupera por UUID.
- ``get_random`` — amostra N personas aleatórias para alocar agentes.
- ``count`` — total persistido.
- ``list_paginated`` — paginação para a API.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Final
from uuid import UUID

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from melicrowd.personas.models import IncomeClass, Persona
from melicrowd.personas.orm import PersonaORM

LOGGER: Final = logger.bind(module="personas.repository")


class PersonaRepository:
    """Repository async para personas. Recebe a sessão por DI."""

    def __init__(self, session: AsyncSession) -> None:
        """Inicializa o repository.

        Args:
            session: sessão async aberta. O caller controla commit/rollback.
        """
        self.session = session

    async def create_batch(self, personas: Sequence[Persona]) -> int:
        """Insere todas as personas em uma única transação.

        Args:
            personas: sequência de Persona Pydantic validadas.

        Returns:
            Número de linhas inseridas.
        """
        if not personas:
            return 0
        rows = [
            PersonaORM(
                persona_id=p.persona_id,
                name=p.name,
                age=p.age,
                gender=p.gender,
                location_state=p.location_state,
                location_city=p.location_city,
                income_class=p.income_class.value,
                occupation=p.occupation,
                interests=p.interests,
                purchase_drivers=p.purchase_drivers,
                price_sensitivity=p.price_sensitivity,
                brand_loyalty=p.brand_loyalty,
                risk_tolerance=p.risk_tolerance,
                digital_savviness=p.digital_savviness,
                avg_session_duration_min=p.avg_session_duration_min,
                weekly_visit_frequency=p.weekly_visit_frequency,
                preferred_categories=p.preferred_categories,
                abandonment_likelihood=p.abandonment_likelihood,
                review_likelihood=p.review_likelihood,
            )
            for p in personas
        ]
        self.session.add_all(rows)
        await self.session.flush()
        LOGGER.debug("personas batch persisted", extra={"count": len(rows)})
        return len(rows)

    async def get_by_id(self, persona_id: UUID) -> Persona | None:
        """Retorna persona por ID, ou ``None`` se não existir."""
        stmt = select(PersonaORM).where(PersonaORM.persona_id == persona_id)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        return _to_pydantic(row) if row else None

    async def get_random(self, n: int) -> list[Persona]:
        """Retorna N personas aleatórias (uso: alocar a agentes)."""
        if n <= 0:
            return []
        stmt = select(PersonaORM).order_by(func.random()).limit(n)
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return [_to_pydantic(r) for r in rows]

    async def count(self) -> int:
        """Conta total de personas persistidas."""
        stmt = select(func.count()).select_from(PersonaORM)
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def list_paginated(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        income_class: IncomeClass | None = None,
        location_state: str | None = None,
    ) -> list[Persona]:
        """Lista paginada com filtros opcionais.

        Args:
            offset: índice inicial.
            limit: máximo por página.
            income_class: filtra por classe social.
            location_state: filtra por UF (case-insensitive).

        Returns:
            Lista de personas (até ``limit`` itens).
        """
        stmt = select(PersonaORM).order_by(PersonaORM.created_at.desc())
        if income_class is not None:
            stmt = stmt.where(PersonaORM.income_class == income_class.value)
        if location_state is not None:
            stmt = stmt.where(PersonaORM.location_state == location_state.upper())
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return [_to_pydantic(r) for r in rows]


def _to_pydantic(row: PersonaORM) -> Persona:
    """Converte ORM row → Persona Pydantic."""
    return Persona(
        persona_id=row.persona_id,
        name=row.name,
        age=row.age,
        gender=row.gender,  # type: ignore[arg-type]
        location_state=row.location_state,
        location_city=row.location_city,
        income_class=IncomeClass(row.income_class),
        occupation=row.occupation,
        interests=row.interests,
        purchase_drivers=row.purchase_drivers,
        price_sensitivity=row.price_sensitivity,
        brand_loyalty=row.brand_loyalty,
        risk_tolerance=row.risk_tolerance,
        digital_savviness=row.digital_savviness,
        avg_session_duration_min=row.avg_session_duration_min,
        weekly_visit_frequency=row.weekly_visit_frequency,
        preferred_categories=row.preferred_categories,
        abandonment_likelihood=row.abandonment_likelihood,
        review_likelihood=row.review_likelihood,
        created_at=row.created_at,
    )
