"""Templates de prompt da camada Agent."""
from __future__ import annotations

from importlib import resources
from typing import Final


def _load(name: str) -> str:
    return (resources.files("melicrowd.agents.prompts") / name).read_text(encoding="utf-8")


DECIDE_SESSION: Final[str] = _load("decide_session.txt")
EVALUATE_ITEM: Final[str] = _load("evaluate_item.txt")
CHECKOUT_DECISION: Final[str] = _load("checkout_decision.txt")
WRITE_REVIEW: Final[str] = _load("write_review.txt")
