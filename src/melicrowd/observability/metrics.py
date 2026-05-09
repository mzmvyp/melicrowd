"""Métricas Prometheus do MeliCrowd.

Convenções:
- Prefixo ``melicrowd_`` em todos os nomes.
- Labels apenas em cardinality baixa (outcome, node, persona_class).
- Histograms com buckets calibrados pra p50-p99 reais.

Métricas vivem em registry global (default do prometheus-client). O endpoint
``/metrics`` da API e do orchestrator (porta 9092) expõem o snapshot.
"""
from __future__ import annotations

from typing import Final

from prometheus_client import Counter, Gauge, Histogram

# -----------------------------------------------------------------------------
# Counters
# -----------------------------------------------------------------------------

sessions_started_total: Final = Counter(
    "melicrowd_sessions_started_total",
    "Total de sessões iniciadas pelo orchestrator.",
    labelnames=("persona_class", "intent"),
)

sessions_completed_total: Final = Counter(
    "melicrowd_sessions_completed_total",
    "Total de sessões finalizadas, segregado por outcome.",
    labelnames=("outcome",),
)

qwen_calls_total: Final = Counter(
    "melicrowd_qwen_calls_total",
    "Total de chamadas ao Qwen por nó.",
    labelnames=("node", "fallback_used"),
)

qwen_errors_total: Final = Counter(
    "melicrowd_qwen_errors_total",
    "Total de erros do Qwen, segregado por tipo.",
    labelnames=("error_type",),
)

melisim_calls_total: Final = Counter(
    "melicrowd_melisim_calls_total",
    "Total de chamadas ao api-gateway do Melisim.",
    labelnames=("endpoint", "status"),
)

# -----------------------------------------------------------------------------
# Histograms (latency / value)
# -----------------------------------------------------------------------------

session_duration_seconds: Final = Histogram(
    "melicrowd_session_duration_seconds",
    "Duração total de uma sessão de agente.",
    labelnames=("outcome",),
    buckets=(10, 30, 60, 120, 300, 600, 1200, 1800, 3600),
)

qwen_latency_seconds: Final = Histogram(
    "melicrowd_qwen_latency_seconds",
    "Latência de uma chamada Qwen (inclui espera no semaphore).",
    labelnames=("node",),
    buckets=(0.5, 1, 2, 5, 10, 20, 30, 60, 120),
)

melisim_latency_seconds: Final = Histogram(
    "melicrowd_melisim_latency_seconds",
    "Latência de chamadas HTTP ao Melisim.",
    labelnames=("endpoint",),
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
)

cart_value_brl: Final = Histogram(
    "melicrowd_cart_value_brl",
    "Valor total do carrinho ao final da sessão.",
    labelnames=("outcome",),
    buckets=(0, 50, 100, 250, 500, 1000, 2500, 5000, 10000),
)

# -----------------------------------------------------------------------------
# Gauges
# -----------------------------------------------------------------------------

active_agents: Final = Gauge(
    "melicrowd_active_agents",
    "Número de workers do pool ativos no momento.",
)

qwen_in_flight: Final = Gauge(
    "melicrowd_qwen_in_flight",
    "Chamadas Qwen executando agora.",
)

qwen_waiting: Final = Gauge(
    "melicrowd_qwen_waiting",
    "Chamadas Qwen aguardando vaga no semaphore.",
)

agents_per_state: Final = Gauge(
    "melicrowd_agents_per_state",
    "Quantidade de agentes em cada nó do grafo.",
    labelnames=("state",),
)
