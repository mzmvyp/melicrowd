"""Alembic environment — bootstrap síncrono via SQLAlchemy 2.x.

O DSN é lido de ``MELICROWD_POSTGRES_DSN_SYNC`` (não usar o async aqui;
Alembic não suporta drivers asyncpg nativamente sem `run_sync`).
"""
from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from melicrowd.config import settings
from melicrowd.personas.orm import Base as PersonasBase
from melicrowd.sellers import orm as _sellers_orm  # noqa: F401  (registers SellerPersonaORM/SellerSessionORM)
from melicrowd.sessions import orm as _sessions_orm  # noqa: F401  (registers SessionORM/DecisionORM tables)
from melicrowd.tech_lead import orm as _tech_lead_orm  # noqa: F401  (registers TaskORM)

# Alembic Config object.
config = context.config

# Inject DSN from settings (which loads from .env or env vars).
config.set_main_option("sqlalchemy.url", settings.postgres_dsn_sync)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Populated as more domains add ORM models. Autogenerate compares this MetaData
# against the live DB to detect drift. Phase 2 wires only the personas Base.
target_metadata = PersonasBase.metadata


def run_migrations_offline() -> None:
    """Roda migrations no modo 'offline' (gera SQL sem conexão)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema="melicrowd",
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Roda migrations no modo 'online' (conexão ao banco)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema="melicrowd",
            include_schemas=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
