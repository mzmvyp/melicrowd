"""Testes do logging setup."""
from __future__ import annotations

import melicrowd.logging_setup as lm
from melicrowd.logging_setup import configure_logging


def test_configure_logging_is_idempotent() -> None:
    # First call configures.
    lm._CONFIGURED = False
    configure_logging()
    assert lm._CONFIGURED is True

    # Second call is a no-op (no exception, still configured).
    configure_logging()
    assert lm._CONFIGURED is True
