"""Estado de uma sessão de vendedor (vive em memória durante o run)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

from melicrowd.sellers.models import SellerPersona, SellerProduct, StockAlert


@dataclass(slots=True)
class SellerSessionState:
    """Estado leve de uma sessão de vendedor (não vai pro LangGraph)."""

    seller_persona: SellerPersona
    session_id: UUID = field(default_factory=uuid4)
    worker_id: str | None = None

    # Auth state
    melisim_user_id: str | None = None
    auth_token: str | None = None

    # Decisão macro (Qwen #1)
    session_focus: str | None = None
    plan_create_n: int = 0
    plan_update_prices_n: int = 0

    # Snapshots
    inventory: list[SellerProduct] = field(default_factory=list)
    pending_alerts: list[StockAlert] = field(default_factory=list)

    # Contadores de ação
    products_audited: int = 0
    notifications_handled: int = 0
    products_created: int = 0
    products_restocked: int = 0
    products_suspended: int = 0
    prices_updated: int = 0

    # Telemetria
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: datetime | None = None
    qwen_calls_count: int = 0
    melisim_calls_count: int = 0
    errors_encountered: list[str] = field(default_factory=list)
