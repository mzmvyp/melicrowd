"""Scheduler — escolhe persona, executa sessão, persiste, publica Kafka.

Encapsula o fluxo completo de UMA sessão para o ``AgentPool`` chamar em loop.
Mantém estado mínimo (counter de sessões por persona, para rotação de auth).
"""
from __future__ import annotations

import random
from collections import defaultdict
from typing import Final
from uuid import UUID, uuid4

from loguru import logger

from melicrowd.agents.runner import run_session
from melicrowd.agents.state import AgentState
from melicrowd.config import settings
from melicrowd.db import get_session_factory
from melicrowd.execution.kafka_publisher import get_publisher
from melicrowd.observability.hooks import on_session_completed, on_session_started
from melicrowd.observability.live_tracker import get_tracker
from melicrowd.personas.models import Persona
from melicrowd.personas.repository import PersonaRepository
from melicrowd.sessions.repository import SessionRepository

LOGGER: Final = logger.bind(module="orchestrator.scheduler")


class SessionScheduler:
    """Roda 1 sessão completa: pick persona → run → persist → publish."""

    def __init__(self) -> None:
        self._sessions_per_persona: dict[UUID, int] = defaultdict(int)

    async def run_one(self, *, worker_id: str | None = None) -> AgentState | None:
        """Executa 1 sessão e persiste tudo. Retorna ``None`` se sem personas.

        Args:
            worker_id: identificador estável do worker do pool (ex.: ``agent-007``).
                Repassado ao runner/tracker para manter o mesmo dot visual
                no Live Floor entre sessões. Pool faz o ``mark_idle`` depois.
        """
        persona = await self._pick_persona()
        if persona is None:
            return None

        publisher = get_publisher()
        self._sessions_per_persona[persona.persona_id] += 1

        # Publica session_started IMEDIATAMENTE, com o state inicial — antes de
        # rodar a sessão. Assim o timestamp de ingestão no data lake é o início
        # real e, se a sessão crashar no meio, o evento "started" ainda foi emitido.
        # O mesmo session_id é repassado ao runner para casar started/ended.
        sid = uuid4()
        initial_state = AgentState(session_id=sid, persona=persona, worker_id=worker_id)
        on_session_started(initial_state)
        await publisher.session_started(initial_state)

        try:
            final_state = await run_session(persona, session_id=sid, worker_id=worker_id)
            for record in final_state.decision_trace:
                await publisher.decision_made(final_state, record)
            await publisher.session_ended(final_state)
            await self._persist(final_state)
            on_session_completed(final_state)
            tracker = get_tracker()
            await tracker.record_completion(
                final_state.outcome.value if final_state.outcome else "error"
            )
            # NÃO remover do tracker aqui: o AgentPool fará ``mark_idle(worker_id)``
            # entre sessões para preservar o dot visual estável.
            return final_state
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception(
                "scheduler session failed",
                extra={"persona_id": str(persona.persona_id), "error": str(exc)[:200]},
            )
            return None

    async def _pick_persona(self) -> Persona | None:
        factory = get_session_factory()
        async with factory() as db:
            repo = PersonaRepository(db)
            sample = await repo.get_random(1)
        return sample[0] if sample else None

    async def _persist(self, final_state: AgentState) -> None:
        factory = get_session_factory()
        async with factory() as db:
            repo = SessionRepository(db)
            await repo.persist_session(final_state)
            await db.commit()

    @property
    def session_recycle_wait(self) -> float:
        """Tempo de espera entre sessões consecutivas (think time inter-sessão)."""
        return random.uniform(
            settings.session_recycle_min_seconds,
            settings.session_recycle_max_seconds,
        )
