"""Estado do agente (Pydantic).

LangGraph usa este modelo como ``State`` do grafo. Cada nó recebe a instância
e retorna um dict com os campos atualizados (LangGraph faz merge).

Persistência:
- **Live (sessão em vôo)**: Redis via checkpointer (TTL 1h).
- **Finalizado**: linha em ``melicrowd.sessions`` no Postgres (Fase 5/7).
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from melicrowd.personas.models import Persona


class SessionIntent(str, Enum):
    """Intenção macro da sessão (decidida no início via Qwen)."""

    BROWSE = "browse"
    RESEARCH = "research"
    PURCHASE = "purchase"
    COMPARE = "compare"


class SessionOutcome(str, Enum):
    """Resultado final da sessão."""

    PURCHASED = "purchased"
    ABANDONED_CART = "abandoned_cart"
    BROWSED_ONLY = "browsed_only"
    BOUNCED = "bounced"
    ERROR = "error"


class CartItem(BaseModel):
    """Item do carrinho do agente (em memória, Melisim não tem cart server-side)."""

    product_id: str
    title: str
    price: float = Field(ge=0)
    quantity: int = Field(default=1, ge=1)


class Product(BaseModel):
    """Produto retornado pelo Melisim (subset de campos relevantes)."""

    product_id: str
    title: str
    price: float
    category: str = ""
    brand: str = ""
    rating: float = 0.0
    review_count: int = 0
    stock: int = 0


class DecisionRecord(BaseModel):
    """Registro de uma chamada Qwen (parte do trace persistido em Postgres)."""

    decision_id: UUID = Field(default_factory=uuid4)
    node: str
    prompt_chars: int
    response_keys: list[str] = Field(default_factory=list)
    latency_ms: int
    fallback_used: bool = False
    error: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgentState(BaseModel):
    """Estado completo de um agente em sessão.

    LangGraph serializa via Pydantic; Redis checkpointer guarda essa instância.

    Atributos:
        session_id: UUID4 único da sessão.
        persona: persona alocada ao agente para esta sessão.
        melisim_user_id: ID retornado por POST /auth/register, se a sessão se autenticou.
        auth_token: JWT do Melisim, válido até expirar.
        session_intent: decisão Qwen #1 — define o "porquê" da sessão.
        target_categories: categorias-alvo decididas no início.
        budget_brl: limite de gasto autoimposto pela persona.
        purchase_probability: 0-1, modula transições Markov.
        current_page: nome do nó atual (rastreio).
        viewed_products: lista de product_ids vistos.
        search_queries: queries de busca realizadas.
        cart: itens no carrinho local.
        outcome: ``SessionOutcome`` quando terminada.
        purchase_total_brl: total efetivamente pago.
        started_at / last_action_at: timestamps.
        qwen_calls_count / latency / melisim_calls_count: telemetria.
        errors_encountered: erros que o agente pegou (sem crashar).
        decision_trace: lista de registros de cada chamada Qwen.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    session_id: UUID = Field(default_factory=uuid4)
    persona: Persona
    melisim_user_id: str | None = None
    auth_token: str | None = None

    # Decisões macro (Qwen)
    session_intent: SessionIntent | None = None
    target_categories: list[str] = Field(default_factory=list)
    budget_brl: float | None = None
    purchase_probability: float | None = None

    # Estado de navegação
    current_page: str = "start"
    viewed_products: list[str] = Field(default_factory=list)
    search_queries: list[str] = Field(default_factory=list)
    candidate_products: list[Product] = Field(default_factory=list)
    current_product: Product | None = None
    cart: list[CartItem] = Field(default_factory=list)

    # Decisões intermediárias usadas pelo routing (LangGraph conditional edges)
    last_evaluation: str | None = None  # add_to_cart | back_to_list | exit
    last_continue_decision: str | None = None  # continue | checkout
    last_checkout_decision: str | None = None  # pay | abandon

    # Outcome
    outcome: SessionOutcome | None = None
    purchase_total_brl: float = 0.0

    # Telemetria
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_action_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    qwen_calls_count: int = 0
    qwen_total_latency_ms: int = 0
    melisim_calls_count: int = 0
    errors_encountered: list[str] = Field(default_factory=list)

    # Decision trace (auditoria)
    decision_trace: list[DecisionRecord] = Field(default_factory=list)

    def cart_total(self) -> float:
        """Total acumulado no carrinho (preço × quantidade)."""
        return round(sum(item.price * item.quantity for item in self.cart), 2)

    def record_decision(self, record: DecisionRecord, latency_ms: int) -> None:
        """Adiciona registro de decisão ao trace e incrementa contadores."""
        self.decision_trace.append(record)
        self.qwen_calls_count += 1
        self.qwen_total_latency_ms += latency_ms

    def touch(self) -> None:
        """Atualiza ``last_action_at`` para timestamp atual."""
        self.last_action_at = datetime.now(timezone.utc)


# LangGraph usa AgentState como State graph. Update returned by nodes is dict[str, Any].
NodeUpdate = dict[str, Any]
