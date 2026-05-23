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
    # Qwen é caro. Por default, evaluate_item (3-8 calls/sessão) usa fallback
    # procedural (já modulado por persona). decide_session e checkout_decision
    # continuam usando Qwen — são os pontos de maior impacto narrativo.
    qwen_evaluate_item_enabled: bool = False
    # Mesma lógica: Qwen na decisão de checkout estava devolvendo "abandon"
    # quase sempre (interpretação conservadora do prompt). Procedural com
    # base 0.45 ajustada por intent/persona dá 25-40% conversion consistente.
    qwen_checkout_decision_enabled: bool = False
    qwen_max_output_tokens: int = 256  # num_predict no Ollama
    qwen_temperature: float = 0.3  # baixo = JSON mais confiável
    # Qwen 3 thinking mode: gera 500-2000 tokens de raciocínio ANTES do JSON.
    # Com num_predict pequeno, consome todo o budget e retorna {} vazio.
    # Desativado por default — JSON sai direto, ~3x mais rápido.
    qwen_thinking_enabled: bool = False
    qwen_timeout_seconds: int = Field(default=60, ge=5, le=600)
    # Default 12: mais paralelismo que 4 para AMD/GPU com Ollama; ainda cabe em le=32.
    # Suba via MELICROWD_QWEN_MAX_CONCURRENT se o host aguentar tokens/s sem timeout.
    qwen_max_concurrent: int = Field(default=12, ge=1, le=32)

    # ------------------------------------------------------------------
    # Integração Melisim
    # ------------------------------------------------------------------
    melisim_gateway_url: str = "http://melisim-api-gateway:8000"
    melisim_default_timeout: float = Field(default=5.0, gt=0)
    melisim_rate_limit_per_minute: int = Field(default=100, ge=1)

    # ------------------------------------------------------------------
    # Integração MeliSimLake (Kafka)
    # ------------------------------------------------------------------
    kafka_enabled: bool = True
    kafka_bootstrap_servers: str = "kafka:9092"
    kafka_connect_timeout_seconds: float = 5.0
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
    # Se ``True`` (default), o container ``orchestrator`` sobe um ``AgentPool``
    # ao iniciar. Para Live Floor + ``POST /start`` na **API**, defina ``False``:
    # caso contrário há **dois** pools (API + orchestrator), dois trackers em
    # processos diferentes — o WebSocket só vê o da API; Ollama/DB recebem o dobro da carga.
    orchestrator_autostart: bool = True
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
    # Tech Lead Agent (DeepSeek-V4-pro)
    # ------------------------------------------------------------------
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-v4-pro"
    tech_lead_auto_evaluate_interval_seconds: int = Field(default=300, ge=30)

    # ------------------------------------------------------------------
    # Observabilidade
    # ------------------------------------------------------------------
    log_level: str = "INFO"
    log_json: bool = False
    prometheus_metrics_port: int = Field(default=9091, ge=1024, le=65535)
    otel_exporter_enabled: bool = False
    otel_exporter_otlp_endpoint: str = "http://jaeger:4318"
    otel_service_name: str = "melicrowd"

    # Live Floor: pausa breve após nós **procedurais** (não-Qwen) para a bolinha
    # aparecer no quadrante antes do próximo passo. 0 = desligado (default).
    live_floor_fast_node_delay_seconds: float = Field(default=0.0, ge=0.0, le=10.0)

    # ------------------------------------------------------------------
    # Control plane (FastAPI)
    # ------------------------------------------------------------------
    api_host: str = "0.0.0.0"  # noqa: S104  (intencional: bind em todas interfaces no container)
    api_port: int = Field(default=8101, ge=1024, le=65535)
    api_rate_limit_per_minute: int = Field(default=60, ge=1)


settings: Final[Settings] = Settings()
