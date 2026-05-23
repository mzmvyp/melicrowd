"""Modelos Pydantic da camada Seller."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Final, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

#: UFs brasileiras válidas (espelho do que está em personas/models.py).
VALID_STATES: Final[frozenset[str]] = frozenset(
    {
        "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
        "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
        "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
    }
)


class PriceStrategy(str, Enum):
    """Posicionamento de preço da loja."""

    AGGRESSIVE = "aggressive"  # corta preço pra mover volume
    STANDARD = "standard"
    PREMIUM = "premium"  # alta margem, marca forte


class SellerPersona(BaseModel):
    """Persona de vendedor brasileiro (lojista).

    Atributos comportamentais modulam:
    - quão rápido repõe estoque ao receber notificação
    - quantos produtos novos cria por sessão
    - faixa de preço dos produtos
    - intervalo entre sessões
    """

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    seller_persona_id: UUID = Field(default_factory=uuid4)
    store_name: str = Field(min_length=2, max_length=140)
    owner_name: str = Field(min_length=2, max_length=120)
    location_state: str = Field(min_length=2, max_length=2)
    location_city: str = Field(min_length=2, max_length=120)
    category_focus: list[str] = Field(min_length=1, max_length=6)
    price_strategy: PriceStrategy
    restock_aggressiveness: float = Field(ge=0.0, le=1.0)
    expansion_rate: float = Field(ge=0.0, le=1.0)
    min_catalog_size: int = Field(default=5, ge=1, le=200)
    max_catalog_size: int = Field(default=30, ge=2, le=500)
    session_cooldown_min_seconds: int = Field(default=300, ge=10)
    session_cooldown_max_seconds: int = Field(default=1800, ge=30)
    melisim_user_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("location_state")
    @classmethod
    def _normalize_state(cls, v: str) -> str:
        upper = v.upper()
        if upper not in VALID_STATES:
            msg = f"location_state {v!r} não é uma UF brasileira válida"
            raise ValueError(msg)
        return upper

    @field_validator("category_focus")
    @classmethod
    def _dedup_categories(cls, v: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for c in v:
            normalized = c.strip()
            if normalized and normalized.lower() not in seen:
                seen.add(normalized.lower())
                out.append(normalized)
        return out


class SellerSessionFocus(str, Enum):
    """Foco macro da sessão (decidido pelo Qwen no início)."""

    RESTOCK = "restock"      # priorizar resposta a alertas de estoque
    EXPAND = "expand"        # focar em criar produtos novos
    MAINTENANCE = "maintenance"  # rotina leve, só auditar
    PROMO = "promo"          # mexer em preços


class SellerSessionOutcome(str, Enum):
    OK = "ok"
    PARTIAL = "partial"
    ERROR = "error"


class StockAlert(BaseModel):
    """Notificação de estoque baixo recebida do Melisim."""

    product_id: str
    product_title: str
    current_stock: int
    threshold: int
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SellerProduct(BaseModel):
    """Snapshot de um produto do vendedor (vindo do Melisim)."""

    product_id: str
    seller_id: str | None = None
    title: str
    category: str = ""
    price: float = 0.0
    stock: int = 0
    description: str = ""


class GeneratedProduct(BaseModel):
    """Saída do Qwen para criação de produto."""

    title: str = Field(min_length=3, max_length=140)
    description: str = Field(min_length=10, max_length=1000)
    category: str = Field(min_length=2, max_length=60)
    price_brl: float = Field(gt=0)
    initial_stock: int = Field(ge=1, le=500)


class NotificationDecisionResponse(BaseModel):
    """Saída do Qwen para avaliação de notificação de estoque baixo."""

    action: Literal["restock", "suspend", "ignore"]
    delta: int = Field(default=0, ge=0, le=500)
    reasoning: str = ""


class SessionFocusResponse(BaseModel):
    """Saída do Qwen para escolha do foco da sessão."""

    focus: Literal["restock", "expand", "maintenance", "promo"]
    create_n_products: int = Field(default=0, ge=0, le=5)
    update_n_prices: int = Field(default=0, ge=0, le=10)
    reasoning: str = ""
