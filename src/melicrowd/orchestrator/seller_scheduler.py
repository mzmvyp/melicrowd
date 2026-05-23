"""Scheduler dedicado a vendedores.

Padrão similar ao SessionScheduler dos buyers: pick → run → persist.
Diferenças:
- Persona vem de ``seller_personas`` (não ``personas``)
- Sessão usa ``sellers.runner.run_seller_session`` (loop procedural)
- Cooldown entre sessões é maior (vendedor não fica refresh-clicando)
"""
from __future__ import annotations

import random
from typing import Final

from loguru import logger

from melicrowd.config import settings
from melicrowd.db import get_session_factory
from melicrowd.observability import metrics
from melicrowd.observability.live_tracker import get_tracker
from melicrowd.sellers.models import SellerPersona
from melicrowd.sellers.repository import SellerRepository, SellerSessionRepository
from melicrowd.sellers.runner import run_seller_session, session_outcome
from melicrowd.sellers.state import SellerSessionState

LOGGER: Final = logger.bind(module="orchestrator.seller_scheduler")


class SellerScheduler:
    """Executa 1 sessão de vendedor por chamada de ``run_one``."""

    def __init__(self) -> None:
        pass

    async def run_one(self, *, worker_id: str | None = None) -> SellerSessionState | None:
        """Pick persona → run session → persist. None se não há personas."""
        persona = await self._pick_persona()
        if persona is None:
            return None

        try:
            final_state = await run_seller_session(persona, worker_id=worker_id)
            outcome = session_outcome(final_state)
            await self._persist(final_state, outcome)
            tracker = get_tracker()
            await tracker.record_seller_completion(outcome)
            # Métricas Prometheus
            metrics.seller_sessions_total.labels(outcome=outcome).inc()
            if final_state.products_created:
                metrics.seller_actions_total.labels(action="create").inc(final_state.products_created)
                metrics.seller_products_created_total.inc(final_state.products_created)
            if final_state.products_restocked:
                metrics.seller_actions_total.labels(action="restock").inc(final_state.products_restocked)
                metrics.seller_notifications_responded_total.labels(action="restock").inc(
                    final_state.products_restocked
                )
            if final_state.products_suspended:
                metrics.seller_actions_total.labels(action="suspend").inc(final_state.products_suspended)
                metrics.seller_notifications_responded_total.labels(action="suspend").inc(
                    final_state.products_suspended
                )
            if final_state.prices_updated:
                metrics.seller_actions_total.labels(action="update_price").inc(final_state.prices_updated)
            if final_state.notifications_handled:
                metrics.seller_notifications_received_total.inc(final_state.notifications_handled)
            return final_state
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception(
                "seller session crashed",
                extra={"persona_id": str(persona.seller_persona_id), "error": str(exc)[:200]},
            )
            return None

    async def _pick_persona(self) -> SellerPersona | None:
        factory = get_session_factory()
        async with factory() as db:
            repo = SellerRepository(db)
            sample = await repo.get_random(1)
        return sample[0] if sample else None

    async def _persist(self, state: SellerSessionState, outcome: str) -> None:
        factory = get_session_factory()
        async with factory() as db:
            repo = SellerSessionRepository(db)
            await repo.persist(state, outcome)
            await db.commit()

    @property
    def session_recycle_wait(self) -> float:
        """Cooldown longo (vendedor não fica conectado o tempo todo)."""
        # Reusa range da config (ajustar via .env se quiser cooldown maior pra sellers).
        return random.uniform(
            max(60, settings.session_recycle_min_seconds * 3),
            max(300, settings.session_recycle_max_seconds * 3),
        )
