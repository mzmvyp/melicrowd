"""Schemas request/response da API de Personas."""
from __future__ import annotations

from typing import Final

from pydantic import BaseModel, Field

from melicrowd.personas.models import Persona

MAX_GENERATE_COUNT: Final[int] = 2000


class GenerateRequest(BaseModel):
    """Body do POST /personas/generate."""

    count: int = Field(default=200, ge=1, le=MAX_GENERATE_COUNT)


class GenerateResponse(BaseModel):
    """Resposta do POST /personas/generate."""

    requested: int
    delivered: int
    sample: list[Persona] = Field(default_factory=list, description="primeiras 5 personas geradas")


class PersonaListResponse(BaseModel):
    """Resposta do GET /personas."""

    total: int
    offset: int
    limit: int
    items: list[Persona]
