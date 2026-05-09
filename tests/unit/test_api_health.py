"""Smoke test do endpoint /health da API."""
from __future__ import annotations

from fastapi.testclient import TestClient

from melicrowd.api.main import app


def test_health_returns_ok() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_status_returns_pool_stub() -> None:
    client = TestClient(app)
    response = client.get("/status")
    assert response.status_code == 200
    body = response.json()
    assert body["pool"]["running"] is False
    assert body["pool"]["active_agents"] == 0


def test_metrics_endpoint_serves_prometheus_format() -> None:
    client = TestClient(app)
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
