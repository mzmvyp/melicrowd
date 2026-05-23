"""Templates de prompt do Tech Lead Agent."""
from __future__ import annotations

from importlib import resources
from typing import Final


def _load(name: str) -> str:
    return (resources.files("melicrowd.tech_lead.prompts") / name).read_text(encoding="utf-8")


GENERATE_TASK: Final[str] = _load("generate_task.txt")
EVALUATE_FEEDBACK: Final[str] = _load("evaluate_feedback.txt")
