"""Testes da configuração centralizada.

Smoke test da Fase 1: garante que ``Settings`` carrega defaults sensatos
e que validações Pydantic protegem contra valores inválidos.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from melicrowd.config import Settings


def test_settings_loads_with_defaults() -> None:
    s = Settings()
    assert s.qwen_model == "qwen3:14b"
    assert s.qwen_max_concurrent == 12
    assert s.orchestrator_autostart is True
    assert s.default_agent_count == 50
    assert s.api_port == 8101
    assert s.prometheus_metrics_port == 9091


def test_settings_rate_injection_bounded() -> None:
    s = Settings()
    assert 0.0 <= s.timeout_injection_rate <= 1.0
    assert 0.0 <= s.form_error_injection_rate <= 1.0


def test_settings_rejects_invalid_qwen_concurrency() -> None:
    with pytest.raises(ValidationError):
        Settings(qwen_max_concurrent=0)


def test_settings_rejects_invalid_agent_count() -> None:
    with pytest.raises(ValidationError):
        Settings(default_agent_count=0)


def test_settings_rejects_invalid_injection_rate() -> None:
    with pytest.raises(ValidationError):
        Settings(timeout_injection_rate=1.5)


def test_settings_kafka_topics_namespaced() -> None:
    s = Settings()
    assert s.kafka_topic_session_started.startswith("events.simulator.")
    assert s.kafka_topic_decision_made.startswith("events.simulator.")
    assert s.kafka_topic_session_ended.startswith("events.simulator.")
