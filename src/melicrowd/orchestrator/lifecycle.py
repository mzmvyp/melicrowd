"""Lifecycle helpers — instala signal handlers para graceful shutdown."""
from __future__ import annotations

import asyncio
import signal
from typing import Final

from loguru import logger

LOGGER: Final = logger.bind(module="orchestrator.lifecycle")


def install_signal_handlers(shutdown_event: asyncio.Event) -> None:
    """Roteia SIGTERM/SIGINT para ``shutdown_event``."""
    loop = asyncio.get_running_loop()

    def _handle(signum: int) -> None:
        LOGGER.info("signal received", extra={"signal": signum})
        shutdown_event.set()

    for sig_name in ("SIGTERM", "SIGINT"):
        sig = getattr(signal, sig_name, None)
        if sig is None:
            continue
        try:
            loop.add_signal_handler(sig, _handle, sig)
        except NotImplementedError:
            # Windows: signal handlers não funcionam pra SIGTERM.
            LOGGER.debug("signal handler not supported on this platform", extra={"signal": sig_name})
