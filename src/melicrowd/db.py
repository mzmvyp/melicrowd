"""Engine SQLAlchemy assíncrono e factory de sessões.

O MeliCrowd usa **um único engine async** por processo (asyncpg + SQLAlchemy 2.x).
O engine é criado lazy na primeira chamada e reutilizado.

Para testes, ``override_engine()`` permite injetar um engine apontando para
o testcontainer.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Final

from loguru import logger
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from melicrowd.config import settings

LOGGER: Final = logger.bind(module="db")

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Retorna o engine async global. Cria na primeira chamada."""
    global _engine  # noqa: PLW0603
    if _engine is None:
        _engine = create_async_engine(
            settings.postgres_dsn,
            echo=False,
            pool_size=10,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=300,
        )
        LOGGER.debug("async engine created", extra={"dsn_host": settings.postgres_dsn.split("@")[-1]})
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Retorna a factory global de sessões async."""
    global _session_factory  # noqa: PLW0603
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


async def session_scope() -> AsyncIterator[AsyncSession]:
    """Context manager async que abre/fecha uma sessão.

    Yields:
        ``AsyncSession`` aberta. Commit/rollback são manuais.

    Exemplo:
        ```python
        async for session in session_scope():
            await session.execute(...)
            await session.commit()
        ```
    """
    factory = get_session_factory()
    async with factory() as session:
        yield session


def override_engine(engine: AsyncEngine) -> None:
    """Substitui o engine global (uso restrito a testes)."""
    global _engine, _session_factory  # noqa: PLW0603
    _engine = engine
    _session_factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def dispose_engine() -> None:
    """Fecha o engine. Chamar no shutdown do app."""
    global _engine, _session_factory  # noqa: PLW0603
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        LOGGER.debug("async engine disposed")
