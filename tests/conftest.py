"""Pytest fixtures globais.

Hospeda fixtures que valem para múltiplos arquivos de teste.
Fixtures específicas de unit/integration/e2e ficam nos seus respectivos
``conftest.py`` locais.
"""
from __future__ import annotations

import pytest

from melicrowd.logging_setup import configure_logging


@pytest.fixture(autouse=True, scope="session")
def _configure_logging() -> None:
    """Garante logging configurado em qualquer suíte (silencia uvicorn etc)."""
    configure_logging()
