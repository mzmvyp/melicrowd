"""Templates de prompt da camada Persona."""
from __future__ import annotations

from importlib import resources
from typing import Final

PERSONA_V1: Final[str] = (
    resources.files("melicrowd.personas.prompts") / "persona_v1.txt"
).read_text(encoding="utf-8")
