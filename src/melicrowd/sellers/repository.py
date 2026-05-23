"""Repository async para sellers (personas + sessions)."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Final
from uuid import UUID

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from melicrowd.sellers.models import PriceStrategy, SellerPersona
from melicrowd.sellers.orm import SellerPersonaORM, SellerSessionORM
from melicrowd.sellers.state import SellerSessionState

LOGGER: Final = logger.bind(module="sellers.repository")


class SellerRepository:
    """Persistência de personas seller."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_batch(self, personas: Sequence[SellerPersona]) -> int:
        if not personas:
            return 0
        rows = [
            SellerPersonaORM(
                seller_persona_id=p.seller_persona_id,
                store_name=p.store_name,
                owner_name=p.owner_name,
                location_state=p.location_state,
                location_city=p.location_city,
                category_focus=p.category_focus,
                price_strategy=p.price_strategy.value,
                restock_aggressiveness=p.restock_aggressiveness,
                expansion_rate=p.expansion_rate,
                min_catalog_size=p.min_catalog_size,
                max_catalog_size=p.max_catalog_size,
                session_cooldown_min_seconds=p.session_cooldown_min_seconds,
                session_cooldown_max_seconds=p.session_cooldown_max_seconds,
                melisim_user_id=p.melisim_user_id,
            )
            for p in personas
        ]
        self.session.add_all(rows)
        await self.session.flush()
        return len(rows)

    async def get_random(self, n: int) -> list[SellerPersona]:
        if n <= 0:
            return []
        stmt = select(SellerPersonaORM).order_by(func.random()).limit(n)
        result = await self.session.execute(stmt)
        return [_to_pydantic(r) for r in result.scalars().all()]

    async def get_by_id(self, persona_id: UUID) -> SellerPersona | None:
        stmt = select(SellerPersonaORM).where(SellerPersonaORM.seller_persona_id == persona_id)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        return _to_pydantic(row) if row else None

    async def count(self) -> int:
        stmt = select(func.count()).select_from(SellerPersonaORM)
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def list_paginated(self, *, offset: int = 0, limit: int = 50) -> list[SellerPersona]:
        stmt = (
            select(SellerPersonaORM)
            .order_by(SellerPersonaORM.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [_to_pydantic(r) for r in result.scalars().all()]

    async def update_melisim_user_id(self, persona_id: UUID, user_id: str) -> None:
        stmt = select(SellerPersonaORM).where(SellerPersonaORM.seller_persona_id == persona_id)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is not None:
            row.melisim_user_id = user_id
            await self.session.flush()


class SellerSessionRepository:
    """Persistência de sessions de seller."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def persist(self, state: SellerSessionState, outcome: str) -> None:
        ended_at = state.ended_at or datetime.now(timezone.utc)
        duration = max(0, int((ended_at - state.started_at).total_seconds()))
        row = SellerSessionORM(
            session_id=state.session_id,
            seller_persona_id=state.seller_persona.seller_persona_id,
            melisim_user_id=state.melisim_user_id,
            session_focus=state.session_focus,
            outcome=outcome,
            products_audited=state.products_audited,
            notifications_handled=state.notifications_handled,
            products_created=state.products_created,
            products_restocked=state.products_restocked,
            products_suspended=state.products_suspended,
            prices_updated=state.prices_updated,
            started_at=state.started_at,
            ended_at=ended_at,
            duration_seconds=duration,
            qwen_calls_count=state.qwen_calls_count,
            melisim_calls_count=state.melisim_calls_count,
            errors_encountered=state.errors_encountered,
        )
        self.session.add(row)
        await self.session.flush()


def _to_pydantic(row: SellerPersonaORM) -> SellerPersona:
    return SellerPersona(
        seller_persona_id=row.seller_persona_id,
        store_name=row.store_name,
        owner_name=row.owner_name,
        location_state=row.location_state,
        location_city=row.location_city,
        category_focus=row.category_focus,
        price_strategy=PriceStrategy(row.price_strategy),
        restock_aggressiveness=row.restock_aggressiveness,
        expansion_rate=row.expansion_rate,
        min_catalog_size=row.min_catalog_size,
        max_catalog_size=row.max_catalog_size,
        session_cooldown_min_seconds=row.session_cooldown_min_seconds,
        session_cooldown_max_seconds=row.session_cooldown_max_seconds,
        melisim_user_id=row.melisim_user_id,
        created_at=row.created_at,
    )
