"""Cliente HTTP real para o api-gateway do Melisim.

Usa ``httpx.AsyncClient`` com:
- Connection pooling (keep-alive).
- Retry tenacity em erros transitórios (3 tentativas, backoff exponencial).
- Token bucket compartilhado (respeita rate limit do gateway).
- Error injection (5% timeouts, 2% form errors).
- Telemetria: latência registrada por endpoint.

Para dev/demo sem Melisim rodando, use ``StubMelisimClient`` (mesmo interface).

A API pública é estável — Phase 3 nodes não precisam mudar.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Final
from uuid import uuid4

import httpx
from loguru import logger
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from melicrowd.agents.state import Product
from melicrowd.config import settings
from melicrowd.execution import error_injection
from melicrowd.execution.rate_limiter import get_melisim_bucket

LOGGER: Final = logger.bind(module="execution.melisim_client")

DEFAULT_HEADERS: Final[dict[str, str]] = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MeliCrowd/0.1 (+simulated buyer)",
    "Accept": "application/json",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.5",
}


@dataclass(slots=True)
class AuthResult:
    user_id: str
    access_token: str


@dataclass(slots=True)
class OrderResult:
    order_id: str
    total_amount: float
    status: str


# -----------------------------------------------------------------------------
# Real client
# -----------------------------------------------------------------------------


class MelisimClient:
    """Cliente real para o api-gateway do Melisim."""

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.melisim_gateway_url).rstrip("/")
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            limits = httpx.Limits(max_connections=100, max_keepalive_connections=50)
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=settings.melisim_default_timeout,
                limits=limits,
                headers=DEFAULT_HEADERS,
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @staticmethod
    def _retry_policy() -> AsyncRetrying:
        return AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
            retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
            reraise=True,
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        auth_token: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        await get_melisim_bucket().acquire()
        error_injection.maybe_raise_timeout(path)

        headers: dict[str, str] = {}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        client = await self._get_client()
        async for attempt in self._retry_policy():
            with attempt:
                response = await client.request(method, path, json=json, params=params, headers=headers or None)
                response.raise_for_status()
                if not response.content:
                    return {}
                return response.json()
        return {}  # unreachable, satisfy mypy

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    async def signup(self, name: str, email: str, password: str) -> AuthResult:
        """POST /api/v1/auth/register (BUYER)."""
        payload = error_injection.maybe_inject_form_payload_corruption(
            {"name": name, "email": email, "password": password, "userType": "BUYER"}
        )
        body = await self._request("POST", "/api/v1/auth/register", json=payload)
        # Melisim register doesn't return token; do login next.
        return await self.login(email, password)

    async def login(self, email: str, password: str) -> AuthResult:
        """POST /api/v1/auth/login → JWT."""
        body = await self._request(
            "POST",
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        return AuthResult(
            user_id=str(body.get("user", {}).get("id") or body.get("id") or ""),
            access_token=str(body.get("accessToken", "")),
        )

    # ------------------------------------------------------------------
    # Products
    # ------------------------------------------------------------------

    async def search_products(
        self, query: str, *, limit: int = 20, auth_token: str | None = None
    ) -> list[Product]:
        body = await self._request(
            "GET",
            "/api/v1/products/search",
            params={"q": query, "limit": limit},
            auth_token=auth_token,
        )
        items = body.get("items") or body.get("results") or body.get("products") or []
        return [_parse_product(item) for item in items]

    async def get_product(self, product_id: str, *, auth_token: str | None = None) -> Product:
        body = await self._request(
            "GET", f"/api/v1/products/{product_id}", auth_token=auth_token
        )
        return _parse_product(body)

    async def list_products(
        self, *, page: int = 1, size: int = 20, auth_token: str | None = None
    ) -> list[Product]:
        body = await self._request(
            "GET", "/api/v1/products", params={"page": page, "size": size}, auth_token=auth_token
        )
        items = body.get("items") or []
        return [_parse_product(item) for item in items]

    # ------------------------------------------------------------------
    # Orders & payments
    # ------------------------------------------------------------------

    async def create_order(
        self,
        *,
        buyer_id: str,
        product_id: str,
        quantity: int,
        auth_token: str,
    ) -> OrderResult:
        body = await self._request(
            "POST",
            "/api/v1/orders",
            json={"buyerId": int(buyer_id) if buyer_id.isdigit() else buyer_id, "productId": product_id, "quantity": quantity},
            auth_token=auth_token,
        )
        return OrderResult(
            order_id=str(body.get("id", "")),
            total_amount=float(body.get("totalAmount", 0)),
            status=str(body.get("status", "CREATED")),
        )

    async def pay_order(
        self,
        *,
        order_id: str,
        amount: float,
        method: str = "pix",
        idempotency_key: str | None = None,
        auth_token: str,
    ) -> bool:
        try:
            await self._request(
                "POST",
                "/api/v1/payments",
                json={"order_id": int(order_id) if order_id.isdigit() else order_id, "amount": amount, "method": method},
                auth_token=auth_token,
                idempotency_key=idempotency_key or str(uuid4()),
            )
            return True
        except httpx.HTTPError as exc:
            LOGGER.warning("payment failed", extra={"order_id": order_id, "error": str(exc)[:120]})
            return False

    async def get_order_status(self, order_id: str, *, auth_token: str) -> str:
        body = await self._request(
            "GET", f"/api/v1/orders/{order_id}", auth_token=auth_token
        )
        return str(body.get("status", "UNKNOWN"))


def _parse_product(payload: dict[str, Any]) -> Product:
    """Normaliza payload do Melisim para ``Product``."""
    return Product(
        product_id=str(payload.get("id") or payload.get("product_id") or ""),
        title=str(payload.get("title") or payload.get("name") or ""),
        price=float(payload.get("price", 0)),
        category=str(payload.get("category", "")),
        brand=str(payload.get("brand", "")),
        rating=float(payload.get("rating", 0)),
        review_count=int(payload.get("review_count") or payload.get("reviewCount", 0)),
        stock=int(payload.get("stock", 0)),
    )


# -----------------------------------------------------------------------------
# Stub client (dev/demo sem Melisim rodando)
# -----------------------------------------------------------------------------


_STUB_CATEGORIES = ["eletrônicos", "moda", "casa", "esporte", "livros", "beleza"]
_STUB_BRANDS = ["Samsung", "Apple", "Nike", "Adidas", "Philips", "Brastemp", "LG"]


def _stub_product(query: str = "") -> Product:
    return Product(
        product_id=str(uuid4()),
        title=f"{random.choice(_STUB_BRANDS)} {query or 'Pro'} {random.randint(100, 9999)}",
        price=round(random.uniform(50, 5000), 2),
        category=random.choice(_STUB_CATEGORIES),
        brand=random.choice(_STUB_BRANDS),
        rating=round(random.uniform(3.0, 5.0), 1),
        review_count=random.randint(5, 5000),
        stock=random.randint(0, 200),
    )


class StubMelisimClient(MelisimClient):
    """Implementação stub para dev/demo sem Melisim ativo.

    Reutiliza a interface do client real; substitui apenas as chamadas HTTP
    por dados canned. Útil quando ``make demo`` é rodado sem ``../MeliSim``
    ativo.
    """

    async def signup(self, name: str, email: str, password: str) -> AuthResult:
        return AuthResult(user_id=str(random.randint(1000, 999999)), access_token=f"stub-jwt-{uuid4().hex[:16]}")

    async def login(self, email: str, password: str) -> AuthResult:
        return AuthResult(user_id=str(random.randint(1000, 999999)), access_token=f"stub-jwt-{uuid4().hex[:16]}")

    async def search_products(
        self, query: str, *, limit: int = 20, auth_token: str | None = None
    ) -> list[Product]:
        n = random.randint(5, min(limit, 15))
        return [_stub_product(query) for _ in range(n)]

    async def get_product(self, product_id: str, *, auth_token: str | None = None) -> Product:
        return _stub_product()

    async def list_products(
        self, *, page: int = 1, size: int = 20, auth_token: str | None = None
    ) -> list[Product]:
        return [_stub_product() for _ in range(min(size, 10))]

    async def create_order(
        self,
        *,
        buyer_id: str,
        product_id: str,
        quantity: int,
        auth_token: str,
    ) -> OrderResult:
        return OrderResult(
            order_id=str(uuid4()),
            total_amount=round(random.uniform(100, 2000), 2),
            status="CREATED",
        )

    async def pay_order(self, **_kwargs: Any) -> bool:
        return random.random() < 0.95

    async def get_order_status(self, order_id: str, *, auth_token: str) -> str:
        return "PAID"


# -----------------------------------------------------------------------------
# Singleton management
# -----------------------------------------------------------------------------


_default_client: MelisimClient | None = None


def get_client() -> MelisimClient:
    """Retorna o singleton (cria real client por default)."""
    global _default_client  # noqa: PLW0603
    if _default_client is None:
        _default_client = MelisimClient()
    return _default_client


def set_client(client: MelisimClient) -> None:
    """Substitui o singleton (testes / dev mode com stub)."""
    global _default_client  # noqa: PLW0603
    _default_client = client


def use_stub() -> None:
    """Atalho: substitui o singleton por ``StubMelisimClient``."""
    set_client(StubMelisimClient())
    LOGGER.info("melisim client switched to STUB mode")
