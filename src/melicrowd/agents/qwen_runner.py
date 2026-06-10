"""Helper compartilhado pelos 4 nós Qwen.

Centraliza:
- Render do prompt com placeholders.
- Chamada ao Qwen via ``generate_json`` (já com pool semaphore + retries).
- Captura de exceções → fallback procedural (caller fornece o fallback).
- Registro do trace na ``AgentState``.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, Final, TypeVar

from loguru import logger
from pydantic import BaseModel, ValidationError

from melicrowd.agents.state import AgentState, DecisionRecord
from melicrowd.llm.qwen_client import generate_json
from melicrowd.llm.trace import log_decision
from melicrowd.observability.hooks import on_qwen_call
from melicrowd.observability.live_tracker import get_tracker

LOGGER: Final = logger.bind(module="agents.qwen_runner")

T = TypeVar("T", bound=BaseModel)


def qwen_trace_fields(state: AgentState) -> dict[str, Any]:
    """Campos de trace Qwen para incluir no ``NodeUpdate`` retornado pelo nó.

    **Obrigatório em todo nó que chama ``run_qwen_node``.** LangGraph só
    propaga o que o nó RETORNA — ``record_decision`` muta a cópia local do
    state e essa mutação morre com o nó. Sem devolver estes campos, o
    ``final_state`` chega com ``qwen_calls_count=0`` e ``decision_trace=[]``
    (bug histórico: TODAS as sessões persistidas/Kafka sem trace de decisão,
    replay do Streamlit vazio, eventos "qwen" do Live Floor nunca emitidos).
    """
    return {
        "qwen_calls_count": state.qwen_calls_count,
        "qwen_total_latency_ms": state.qwen_total_latency_ms,
        "decision_trace": state.decision_trace,
    }


async def run_qwen_node(
    *,
    state: AgentState,
    node_name: str,
    prompt: str,
    response_model: type[T],
    fallback: Callable[[AgentState], T],
    max_output_tokens: int | None = None,
) -> T:
    """Roda um nó Qwen com fallback procedural garantido.

    Args:
        state: estado atual do agente (para registrar trace).
        node_name: nome do nó (e.g. "decide_session"). Vai pra trace.
        prompt: prompt completo já renderizado com placeholders.
        response_model: classe Pydantic para validar a resposta.
        fallback: função que retorna uma resposta procedural caso Qwen falhe.
        max_output_tokens: ``num_predict`` da chamada (decisões usam o budget
            menor de ``settings.qwen_decision_max_tokens``).

    Returns:
        Instância validada de ``response_model``. Se Qwen falhou, vem do fallback.
    """
    started = time.monotonic()
    response: T
    fallback_used = False
    error: str | None = None
    raw = ""
    parsed: dict[str, Any] | None = None
    latency_ms = 0

    # Pre-Qwen tracker update: estação Qwen pode demorar 1-6s; sem isso,
    # o Live Floor mostraria o agente parado na estação ANTERIOR durante toda
    # a chamada (o astream(stream_mode="updates") só emite após o nó terminar).
    # Update pre-flight com is_thinking=True faz a bolinha aparecer no nó Qwen
    # com pulse purple imediatamente.
    try:
        await get_tracker().upsert_from_state(
            state,
            worker_id=state.worker_id,
            station_override=node_name,
            is_thinking=True,
            thinking_progress=0.05,
        )
    except Exception:  # noqa: BLE001  — tracker é best-effort
        pass

    try:
        call = await generate_json(prompt, max_output_tokens=max_output_tokens)
        raw = call.raw
        parsed = call.response
        latency_ms = call.latency_ms
        response = response_model.model_validate(call.response)
    except (ValidationError, Exception) as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
        latency_ms = int((time.monotonic() - started) * 1000)
        LOGGER.warning(
            "qwen node falling back",
            extra={"node": node_name, "error": error[:200], "session_id": str(state.session_id)},
        )
        response = fallback(state)
        fallback_used = True

    # Trace: log estruturado + registro na AgentState
    log_decision(
        session_id=state.session_id,
        persona_id=state.persona.persona_id,
        node=node_name,
        prompt=prompt,
        response_parsed=parsed,
        response_raw=raw,
        latency_ms=latency_ms,
        fallback_used=fallback_used,
        error=error,
    )
    record = DecisionRecord(
        node=node_name,
        prompt_chars=len(prompt),
        response_keys=list(response.model_dump().keys()),
        latency_ms=latency_ms,
        fallback_used=fallback_used,
        error=error,
    )
    state.record_decision(record, latency_ms=latency_ms)
    on_qwen_call(record)
    return response
