"""Service layer da camada Persona.

Orquestra generator + repository. É a fronteira que API e CLI consomem.
"""
from __future__ import annotations

from typing import Final
from uuid import UUID

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from melicrowd.personas import generator
from melicrowd.personas.models import IncomeClass, Persona
from melicrowd.personas.repository import PersonaRepository

LOGGER: Final = logger.bind(module="personas.service")


class PersonaService:
    """Use cases da camada Persona."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = PersonaRepository(session)

    async def generate_and_persist(self, count: int) -> list[Persona]:
        """Gera ``count`` personas via Qwen e persiste em batch.

        Args:
            count: alvo de personas válidas.

        Returns:
            Lista de personas persistidas (pode ser menor que ``count`` se
            Qwen falhar repetidamente — log warning emitido nesse caso).
        """
        personas = await generator.generate_batch(count)
        if not personas:
            LOGGER.error("no personas generated — Qwen unavailable?")
            return []

        await self.repository.create_batch(personas)
        await self.session.commit()
        LOGGER.info("personas persisted", extra={"count": len(personas)})
        return personas

    async def list(  # noqa: A003  (deliberadamente paralelo a `list` de Python)
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        income_class: IncomeClass | None = None,
        location_state: str | None = None,
    ) -> list[Persona]:
        """Lista paginada com filtros."""
        return await self.repository.list_paginated(
            offset=offset,
            limit=limit,
            income_class=income_class,
            location_state=location_state,
        )

    async def get(self, persona_id: UUID) -> Persona | None:
        """Recupera 1 persona por UUID."""
        return await self.repository.get_by_id(persona_id)

    async def count(self) -> int:
        """Total persistido."""
        return await self.repository.count()

    async def sample(self, n: int) -> list[Persona]:
        """N personas aleatórias para alocar a agentes."""
        return await self.repository.get_random(n)
