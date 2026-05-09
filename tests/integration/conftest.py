"""Fixtures de integração — testcontainers (Postgres, Redis, Kafka).

Marker `integration` filtra essas suites: ``pytest -m integration``.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker

from melicrowd import db as db_module


@pytest.fixture(scope="session")
def event_loop_policy() -> asyncio.AbstractEventLoopPolicy:
    return asyncio.DefaultEventLoopPolicy()


@pytest_asyncio.fixture(scope="session")
async def pg_url() -> AsyncIterator[str]:
    """Sobe Postgres via testcontainers e aplica migrations."""
    from testcontainers.postgres import PostgresContainer

    container = PostgresContainer("postgres:16.3", username="melicrowd", password="melicrowd123", dbname="melicrowd")
    container.start()
    try:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(5432)
        url = f"postgresql+asyncpg://melicrowd:melicrowd123@{host}:{port}/melicrowd"
        sync_url = f"postgresql+psycopg2://melicrowd:melicrowd123@{host}:{port}/melicrowd"

        # Roda migrations Alembic.
        from alembic import command  # type: ignore[import-not-found]
        from alembic.config import Config

        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", sync_url)
        # Antes do upgrade, cria o schema (init.sql não roda em testcontainers).
        import sqlalchemy as sa

        sync_engine = sa.create_engine(sync_url)
        with sync_engine.connect() as conn:
            conn.execute(sa.text("CREATE SCHEMA IF NOT EXISTS melicrowd"))
            conn.execute(sa.text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
            conn.commit()
        sync_engine.dispose()

        command.upgrade(cfg, "head")

        yield url
    finally:
        container.stop()


@pytest_asyncio.fixture
async def db_session(pg_url: str) -> AsyncIterator[AsyncSession]:
    """Sessão async limpa por teste — rollback no fim."""
    engine = create_async_engine(pg_url, echo=False)
    db_module.override_engine(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()
