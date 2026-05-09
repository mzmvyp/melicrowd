"""Testes do error injection."""
from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from melicrowd.execution import error_injection


def test_should_inject_timeout_zero_rate() -> None:
    with patch("melicrowd.execution.error_injection.settings") as mock_settings:
        mock_settings.timeout_injection_rate = 0.0
        for _ in range(50):
            assert error_injection.should_inject_timeout() is False


def test_should_inject_timeout_full_rate() -> None:
    with patch("melicrowd.execution.error_injection.settings") as mock_settings:
        mock_settings.timeout_injection_rate = 1.0
        for _ in range(20):
            assert error_injection.should_inject_timeout() is True


def test_maybe_raise_timeout_when_rate_full() -> None:
    with patch("melicrowd.execution.error_injection.settings") as mock_settings:
        mock_settings.timeout_injection_rate = 1.0
        with pytest.raises(httpx.TimeoutException):
            error_injection.maybe_raise_timeout("/api/v1/products")


def test_maybe_inject_form_payload_corruption_no_rate() -> None:
    with patch("melicrowd.execution.error_injection.settings") as mock_settings:
        mock_settings.form_error_injection_rate = 0.0
        payload = {"name": "Ana", "email": "ana@test"}
        assert error_injection.maybe_inject_form_payload_corruption(payload) == payload


def test_maybe_inject_form_payload_corruption_full_rate() -> None:
    with patch("melicrowd.execution.error_injection.settings") as mock_settings:
        mock_settings.form_error_injection_rate = 1.0
        payload = {"name": "Ana", "email": "ana@test", "user_id": 42}
        corrupted = error_injection.maybe_inject_form_payload_corruption(payload)
        # ID intacto; pelo menos um campo string ficou vazio.
        assert corrupted["user_id"] == 42
        assert any(v == "" for k, v in corrupted.items() if isinstance(v, str))
