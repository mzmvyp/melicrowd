"""Configuração centralizada do MeliCrowd.

Todas as variáveis de ambiente passam por aqui. Nenhum módulo deve ler
``os.environ`` diretamente — sempre importar ``settings`` deste módulo.

O carregamento é feito por ``pydantic-settings``: lê ``.env`` (se existir),
depois variáveis de ambiente do processo (que sobrescrevem o ``.env``).

Prefixo obrigatório das vars: ``MELICROWD_``. Exemplo:
``MELICROWD_QWEN_MODEL=qwen3:14b``.
"""
from __future__ import annotations

from typing import Final

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_AGENT_COUNT: Final[int] = 50


class Settings(BaseSettings):
    """Settings tipados — fonte única de verdade para configuração runtime.

    Args:
        env_file: Caminho do .env. Default: arquivo na raiz do repo.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="MELICROWD_",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # LLM (Qwen via Ollama)
    # ------------------------------------------------------------------
    qwen_base_url: str = "http://host.docker.internal:11434"
    qwen_model: str = "qwen3:14b"
    qwen_timeout_seconds: int = Field(default=60, ge=5, le=600)
    qwen_max_concurrent: int = Field(default=4, ge=1, le=32)

    # ------------------------------------------------------------------
    # Integração Melisim
    # ------------------------------------------------------------------
    melisim_gateway_url: str = "http://melisim-api-gateway:8000"
    melisim_default_timeout: float = Field(default=5.0, gt=0)
    melisim_rate_limit_per_minute: int = Field(default=100, ge=1)

    # ------------------------------------------------------------------
    # Integração MeliSimLake (Kafka)
    # ------------------------------------------------------------------
    kafka_bootstrap_servers: str = "kafka:9092"
    schema_registry_url: str = "http://schema-registry:8081"
    kafka_topic_session_started: str = "events.simulator.session_started"
    kafka_topic_decision_made: str = "events.simulator.decision_made"
    kafka_topic_session_ended: str = "events.simulator.session_ended"

    # ------------------------------------------------------------------
    # Persistência
    # ------------------------------------------------------------------
    postgres_dsn: str = (
        "postgresql+asyncpg://melicrowd:melicrowd123@postgres-melicrowd:5432/melicrowd"
    )
    postgres_dsn_sync: str = (
        "postgresql+psycopg2://melicrowd:melicrowd123@postgres-melicrowd:5432/melicrowd"
    )
    redis_url: str = "redis://redis-melicrowd:6379/0"
    redis_checkpoint_ttl_seconds: int = Field(default=3600, ge=60)

    # ------------------------------------------------------------------
    # Orchestrator
    # ------------------------------------------------------------------
    default_agent_count: int = Field(default=DEFAULT_AGENT_COUNT, ge=1, le=500)
    session_recycle_min_seconds: int = Field(default=30, ge=1)
    session_recycle_max_seconds: int = Field(default=300, ge=1)
    auth_recycle_every_n_sessions: int = Field(default=5, ge=1)

    # ------------------------------------------------------------------
    # Error injection
    # ------------------------------------------------------------------
    timeout_injection_rate: float = Field(default=0.05, ge=0.0, le=1.0)
    form_error_injection_rate: float = Field(default=0.02, ge=0.0, le=1.0)

    # ------------------------------------------------------------------
    # Observabilidade
    # ------------------------------------------------------------------
    log_level: str = "INFO"
    log_json: bool = False
    prometheus_metrics_port: int = Field(default=9091, ge=1024, le=65535)
    otel_exporter_enabled: bool = False
    otel_exporter_otlp_endpoint: str = "http://jaeger:4318"
    otel_service_name: str = "melicrowd"

    # ------------------------------------------------------------------
    # Control plane (FastAPI)
    # ------------------------------------------------------------------
    api_host: str = "0.0.0.0"  # noqa: S104  (intencional: bind em todas interfaces no container)
    api_port: int = Field(default=8101, ge=1024, le=65535)
    api_rate_limit_per_minute: int = Field(default=60, ge=1)


settings: Final[Settings] = Settings()
