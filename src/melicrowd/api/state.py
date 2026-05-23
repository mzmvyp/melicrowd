"""Estado compartilhado do app FastAPI (pools, locks).

Singleton container que sobrevive ao lifespan da aplicação. Permite que
rotas de controle e inspeção acessem o mesmo ``AgentPool`` (buyers) e
``SellerPool``.
"""
from __future__ import annotations

import asyncio

from melicrowd.orchestrator.pool import AgentPool
from melicrowd.orchestrator.seller_pool import SellerPool


class AppState:
    """State container do app — pools + locks pra mutações concorrentes."""

    def __init__(self) -> None:
        self.pool: AgentPool | None = None
        self.pool_lock = asyncio.Lock()
        # Pool de vendedores — separado dos buyers.
        self.seller_pool: SellerPool | None = None
        self.seller_pool_lock = asyncio.Lock()

    def is_running(self) -> bool:
        return self.pool is not None and self.pool.is_running

    def seller_is_running(self) -> bool:
        return self.seller_pool is not None and self.seller_pool.is_running


_app_state: AppState | None = None


def get_app_state() -> AppState:
    """Retorna o singleton do AppState."""
    global _app_state  # noqa: PLW0603
    if _app_state is None:
        _app_state = AppState()
    return _app_state


def reset_app_state() -> None:
    """Reseta (testes)."""
    global _app_state  # noqa: PLW0603
    _app_state = None
