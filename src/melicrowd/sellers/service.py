"""Service layer pra sellers — orquestra geração + persistência."""
from __future__ import annotations

from typing import Final
from uuid import UUID

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from melicrowd.sellers.models import SellerPersona
from melicrowd.sellers.repository import SellerRepository
from melicrowd.sellers.synthetic import synthetic_seller_personas

LOGGER: Final = logger.bind(module="sellers.service")


class SellerService:
    """Use cases da camada Seller."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = SellerRepository(session)

    async def seed_synthetic(self, count: int) -> list[SellerPersona]:
        """Cria N personas sintéticas (sem LLM)."""
        personas = synthetic_seller_personas(count)
        if personas:
            await self.repository.create_batch(personas)
            await self.session.commit()
            LOGGER.info("seller personas seeded (synthetic)", extra={"count": len(personas)})
        return personas

    async def list(  # noqa: A003
        self, *, offset: int = 0, limit: int = 50
    ) -> list[SellerPersona]:
        return await self.repository.list_paginated(offset=offset, limit=limit)

    async def get(self, persona_id: UUID) -> SellerPersona | None:
        return await self.repository.get_by_id(persona_id)

    async def count(self) -> int:
        return await self.repository.count()

    async def sample(self, n: int) -> list[SellerPersona]:
        return await self.repository.get_random(n)
