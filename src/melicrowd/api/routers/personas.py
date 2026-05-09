"""Router /personas — geração e consulta de personas."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger

from melicrowd.api.deps import get_persona_service
from melicrowd.api.schemas.personas import (
    GenerateRequest,
    GenerateResponse,
    PersonaListResponse,
)
from melicrowd.personas.models import IncomeClass, Persona
from melicrowd.personas.service import PersonaService

router = APIRouter(prefix="/personas", tags=["personas"])
LOGGER = logger.bind(module="api.routers.personas")


@router.post("/generate", response_model=GenerateResponse, status_code=status.HTTP_201_CREATED)
async def generate(
    payload: GenerateRequest,
    service: PersonaService = Depends(get_persona_service),
) -> GenerateResponse:
    """Gera ``count`` personas via Qwen e persiste em batch.

    Pode demorar vários minutos para count alto (Qwen 14B + pool semaphore=4).
    """
    LOGGER.info("personas generate requested", extra={"count": payload.count})
    personas = await service.generate_and_persist(payload.count)
    return GenerateResponse(
        requested=payload.count,
        delivered=len(personas),
        sample=personas[:5],
    )


@router.get("", response_model=PersonaListResponse)
async def list_personas(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    income_class: IncomeClass | None = Query(None),
    location_state: str | None = Query(None, min_length=2, max_length=2),
    service: PersonaService = Depends(get_persona_service),
) -> PersonaListResponse:
    """Lista paginada de personas com filtros opcionais."""
    items = await service.list(
        offset=offset,
        limit=limit,
        income_class=income_class,
        location_state=location_state,
    )
    total = await service.count()
    return PersonaListResponse(total=total, offset=offset, limit=limit, items=items)


@router.get("/{persona_id}", response_model=Persona)
async def get_persona(
    persona_id: UUID,
    service: PersonaService = Depends(get_persona_service),
) -> Persona:
    """Detalhe de uma persona por UUID."""
    persona = await service.get(persona_id)
    if persona is None:
        raise HTTPException(status_code=404, detail=f"persona {persona_id} não encontrada")
    return persona
