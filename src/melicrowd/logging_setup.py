"""Logging estruturado via loguru.

Este módulo é o único lugar que configura o logger global.
Todos os módulos do MeliCrowd usam ``from loguru import logger``.

`print` é proibido (lint enforce — ver ruff.toml regra T20).
"""
from __future__ import annotations

import logging
import sys
from typing import Final

from loguru import logger

from melicrowd.config import settings

_CONFIGURED: bool = False

DEFAULT_FORMAT: Final[str] = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{extra[module]}</cyan> | "
    "<level>{message}</level>"
)


class _InterceptHandler(logging.Handler):
    """Redireciona logs do stdlib (uvicorn, sqlalchemy, ...) para loguru.

    Evita ter dois sistemas de logging com formatação divergente.
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = sys._getframe(6), 6  # type: ignore[attr-defined]
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back  # type: ignore[assignment]
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def configure_logging() -> None:
    """Configura o logger global. Idempotente — chamar quantas vezes quiser."""
    global _CONFIGURED  # noqa: PLW0603
    if _CONFIGURED:
        return

    logger.remove()

    if settings.log_json:
        logger.add(
            sys.stderr,
            level=settings.log_level,
            serialize=True,
            backtrace=True,
            diagnose=False,  # diagnose=True vaza variáveis em produção
        )
    else:
        logger.add(
            sys.stderr,
            level=settings.log_level,
            format=DEFAULT_FORMAT,
            backtrace=True,
            diagnose=False,
            enqueue=False,
        )

    # Default `extra[module]` para logs sem `.bind(module=...)`.
    logger.configure(extra={"module": "melicrowd"})

    # Captura logging do stdlib.
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)
    for noisy in ("uvicorn.access", "uvicorn.error", "sqlalchemy.engine"):
        logging.getLogger(noisy).handlers = [_InterceptHandler()]

    _CONFIGURED = True
    logger.bind(module="logging_setup").info(
        "logging configured",
        extra={"level": settings.log_level, "json": settings.log_json},
    )
