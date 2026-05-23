"""Templates de prompt da camada Seller (Qwen)."""
from __future__ import annotations

from importlib import resources
from typing import Final


def _load(name: str) -> str:
    return (resources.files("melicrowd.sellers.prompts") / name).read_text(encoding="utf-8")


DECIDE_SELLER_SESSION: Final[str] = _load("decide_seller_session.txt")
EVALUATE_NOTIFICATION: Final[str] = _load("evaluate_notification.txt")
GENERATE_PRODUCT: Final[str] = _load("generate_product.txt")
