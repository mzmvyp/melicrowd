"""Dependências FastAPI (Dependency Injection).

Mantém wiring DB ↔ rotas em um único lugar. Cada rota que precisa de DB
declara ``session: AsyncSession = Depends(get_session)``.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from melicrowd.db import get_session_factory
from melicrowd.personas.service import PersonaService


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield uma sessão DB async para a rota. Commit/rollback é manual."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def get_persona_service(
    session: AsyncSession = Depends(get_session),
) -> PersonaService:
    """Constrói ``PersonaService`` com a sessão injetada."""
    return PersonaService(session)
