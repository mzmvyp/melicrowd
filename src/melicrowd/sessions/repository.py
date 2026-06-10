"""Repository para persistir sessões finalizadas + decision trace."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from decimal import Decimal
from typing import Final
from uuid import UUID, uuid4

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from melicrowd.agents.state import AgentState, DecisionRecord
from melicrowd.sessions.orm import DecisionORM, SessionORM

LOGGER: Final = logger.bind(module="sessions.repository")


class SessionRepository:
    """Repository async para sessões + decisions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def persist_session(self, state: AgentState) -> None:
        """Persiste a sessão finalizada e suas decisões em uma transação."""
        ended_at = datetime.now(timezone.utc)
        duration = max(0, int((ended_at - state.started_at).total_seconds()))

        if state.outcome is None:
            outcome_str = "error"
        else:
            outcome_str = state.outcome.value

        session_row = SessionORM(
            session_id=state.session_id,
            persona_id=state.persona.persona_id,
            melisim_user_id=state.melisim_user_id,
            session_intent=state.session_intent.value if state.session_intent else None,
            outcome=outcome_str,
            purchase_total_brl=Decimal(str(state.purchase_total_brl)),
            started_at=state.started_at,
            ended_at=ended_at,
            duration_seconds=duration,
            qwen_calls_count=state.qwen_calls_count,
            qwen_total_latency_ms=state.qwen_total_latency_ms,
            melisim_calls_count=state.melisim_calls_count,
            errors_encountered=state.errors_encountered,
        )
        self.session.add(session_row)
        # Flush da sessão ANTES das decisions (mesma transação): sem
        # relationship() no ORM, o unit-of-work não garante a ordem de INSERT
        # entre mappers — o INSERT de decisions podia preceder o de sessions e
        # violar o FK ``decisions_session_id_fkey``. Latente até decision_trace
        # passar a chegar preenchido (antes vinha sempre vazio).
        await self.session.flush()

        for record in state.decision_trace:
            self.session.add(_decision_to_orm(state.session_id, state.persona.persona_id, record))

        await self.session.flush()
        LOGGER.debug(
            "session persisted",
            extra={
                "session_id": str(state.session_id),
                "outcome": outcome_str,
                "decisions": len(state.decision_trace),
            },
        )

    async def list_recent(self, limit: int = 50) -> Sequence[SessionORM]:
        stmt = select(SessionORM).order_by(SessionORM.ended_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get(self, session_id: UUID) -> SessionORM | None:
        stmt = select(SessionORM).where(SessionORM.session_id == session_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_decisions(self, session_id: UUID) -> Sequence[DecisionORM]:
        stmt = (
            select(DecisionORM)
            .where(DecisionORM.session_id == session_id)
            .order_by(DecisionORM.timestamp.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


def _decision_to_orm(session_id: UUID, persona_id: UUID, record: DecisionRecord) -> DecisionORM:
    return DecisionORM(
        decision_id=record.decision_id or uuid4(),
        session_id=session_id,
        persona_id=persona_id,
        node=record.node,
        prompt="",  # full prompt not stored in AgentState (saved by log_decision); audit trail in Kafka
        response_raw=None,
        response_parsed={"keys": record.response_keys},
        latency_ms=record.latency_ms,
        fallback_used=record.fallback_used,
        error=record.error,
        timestamp=record.timestamp,
    )
