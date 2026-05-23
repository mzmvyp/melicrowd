"""Action: ``auth`` — signup/login do vendedor no Melisim."""
from __future__ import annotations

import random

from loguru import logger

from melicrowd.execution.melisim_client import get_client
from melicrowd.sellers.state import SellerSessionState

LOGGER = logger.bind(module="sellers.actions.auth")


async def run(state: SellerSessionState) -> bool:
    """Autentica o vendedor. Reusa melisim_user_id se já temos um.

    Returns:
        True se sucedeu (state.auth_token populado), False se falhou.
    """
    client = get_client()
    p = state.seller_persona
    suffix = random.randint(10000, 99999)
    name_slug = p.owner_name.lower().replace(" ", ".")
    email = f"seller.{name_slug}+{suffix}@melicrowd.test"
    try:
        # signup faz fallback pra login se já existe — tratamento dentro do client.
        result = await client.signup(name=p.owner_name, email=email, password="melicrowd-seller-pw")
        state.melisim_calls_count += 2  # signup + login interno
        state.melisim_user_id = result.user_id
        state.auth_token = result.access_token
        LOGGER.info(
            "seller authenticated",
            extra={
                "session_id": str(state.session_id),
                "store": p.store_name,
                "user_id": result.user_id,
            },
        )
        return bool(result.access_token)
    except Exception as exc:  # noqa: BLE001  — falha de auth aborta sessão
        LOGGER.warning(
            "seller auth failed",
            extra={"session_id": str(state.session_id), "error": str(exc)[:200]},
        )
        state.errors_encountered.append(f"auth: {type(exc).__name__}")
        return False
