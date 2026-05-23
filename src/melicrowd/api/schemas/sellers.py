"""Schemas request/response da API de Sellers."""
from __future__ import annotations

from typing import Final

from pydantic import BaseModel, Field

from melicrowd.sellers.models import SellerPersona

MAX_SEED_COUNT: Final[int] = 200


class SeedRequest(BaseModel):
    """Body do POST /sellers/seed-synthetic."""

    count: int = Field(default=10, ge=1, le=MAX_SEED_COUNT)


class SeedResponse(BaseModel):
    requested: int
    delivered: int
    sample: list[SellerPersona] = Field(default_factory=list)


class SellerListResponse(BaseModel):
    total: int
    offset: int
    limit: int
    items: list[SellerPersona]


class SellerPoolStartResponse(BaseModel):
    target_workers: int
    active_workers: int
    running: bool


class SellerPoolStopResponse(BaseModel):
    drained_in_seconds: float
    active_workers: int


class SellerPoolScaleResponse(BaseModel):
    previous_size: int
    new_size: int
    active_workers: int


class SellerPoolStatus(BaseModel):
    running: bool
    target_workers: int
    active_workers: int
