"""Decision trace — registro auditável de chamadas Qwen.

Versão Fase 2 grava em logs estruturados. Persistência em Postgres
(tabela ``melicrowd.decisions``) entra na Fase 7 quando os agentes
estiverem rodando sessões reais.
"""
from __future__ import annotations

from typing import Any, Final
from uuid import UUID

from loguru import logger

LOGGER: Final = logger.bind(module="llm.trace")


def log_decision(
    *,
    session_id: UUID | None,
    persona_id: UUID | None,
    node: str,
    prompt: str,
    response_parsed: dict[str, Any] | None,
    response_raw: str | None,
    latency_ms: int,
    fallback_used: bool,
    error: str | None = None,
) -> None:
    """Registra uma decisão (chamada Qwen) em log estruturado.

    Args:
        session_id: ID da sessão, ``None`` em chamadas batch (geração de personas).
        persona_id: ID da persona em sessões; ``None`` em batch.
        node: nó do grafo LangGraph que originou a chamada (ex: "evaluate_item")
            ou contexto batch (ex: "persona_batch").
        prompt: prompt completo enviado ao Qwen.
        response_parsed: resposta JSON parseada, ``None`` se falhou.
        response_raw: texto cru da resposta.
        latency_ms: latência total em ms.
        fallback_used: True se caiu no caminho procedural.
        error: descrição curta do erro, se houver.
    """
    LOGGER.info(
        "decision",
        extra={
            "session_id": str(session_id) if session_id else None,
            "persona_id": str(persona_id) if persona_id else None,
            "node": node,
            "latency_ms": latency_ms,
            "fallback_used": fallback_used,
            "error": error,
            "prompt_chars": len(prompt),
            "response_keys": list(response_parsed.keys()) if response_parsed else [],
        },
    )
