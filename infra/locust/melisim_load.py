"""Locustfile para load test do Melisim.

Uso:
    locust -f infra/locust/melisim_load.py --host=http://localhost:18000

Cenário: BUYER que registra, busca, vê detalhe, cria pedido, paga.
"""
from __future__ import annotations

import random
import uuid

from locust import HttpUser, between, task


class MelisimBuyer(HttpUser):
    wait_time = between(2, 8)
    token: str = ""
    user_id: str = ""

    def on_start(self) -> None:
        suffix = uuid.uuid4().hex[:8]
        email = f"locust+{suffix}@melicrowd.test"
        self.client.post(
            "/api/v1/auth/register",
            json={
                "name": f"Locust {suffix}",
                "email": email,
                "password": "locust-test-pw",
                "userType": "BUYER",
            },
        )
        login = self.client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "locust-test-pw"},
        )
        if login.status_code == 200:
            data = login.json()
            self.token = data.get("accessToken", "")
            self.user_id = str(data.get("user", {}).get("id") or data.get("id") or "")

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    @task(5)
    def search_products(self) -> None:
        q = random.choice(["smart", "tv", "phone", "tenis", "livro"])
        self.client.get(f"/api/v1/products/search?q={q}", name="/products/search")

    @task(3)
    def list_products(self) -> None:
        self.client.get("/api/v1/products?page=1&size=20", name="/products")

    @task(1)
    def buy_flow(self) -> None:
        list_resp = self.client.get("/api/v1/products?page=1&size=5", name="/products")
        if list_resp.status_code != 200:
            return
        items = list_resp.json().get("items") or []
        if not items:
            return
        product = items[0]
        self.client.get(f"/api/v1/products/{product['id']}", name="/products/{id}")

        if not self.token or not self.user_id:
            return
        order_resp = self.client.post(
            "/api/v1/orders",
            json={
                "buyerId": int(self.user_id) if self.user_id.isdigit() else self.user_id,
                "productId": product["id"],
                "quantity": 1,
            },
            headers=self._headers(),
        )
        if order_resp.status_code not in (200, 201):
            return
        order = order_resp.json()
        self.client.post(
            "/api/v1/payments",
            json={
                "order_id": order.get("id"),
                "amount": order.get("totalAmount", 0),
                "method": "pix",
            },
            headers={**self._headers(), "Idempotency-Key": str(uuid.uuid4())},
        )
