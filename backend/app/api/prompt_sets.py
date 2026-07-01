from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_catalog_service, get_prompt_generation_service
from app.schemas.prompt_sets import (
    PromptGenerationRequest,
    PromptGenerationResponse,
    PromptSet,
    PromptSetSummary,
    PromptSetUpsertRequest,
)
from app.services.catalog_service import CatalogService
from app.services.prompt_generation_service import PromptGenerationService


router = APIRouter(prefix="/api/prompt-sets", tags=["prompt-sets"])


@router.get("", response_model=list[PromptSetSummary])
def list_prompt_sets(catalog_service: CatalogService = Depends(get_catalog_service)) -> list[PromptSetSummary]:
    return catalog_service.list_prompt_sets()


@router.get("/{prompt_set_id}", response_model=PromptSet)
def get_prompt_set(
    prompt_set_id: str,
    catalog_service: CatalogService = Depends(get_catalog_service),
) -> PromptSet:
    prompt_set = catalog_service.get_prompt_set(prompt_set_id)
    if prompt_set is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt set not found.")
    return prompt_set


@router.post("/generate", response_model=PromptGenerationResponse)
def generate_prompt_set(
    request: PromptGenerationRequest,
    generation_service: PromptGenerationService = Depends(get_prompt_generation_service),
) -> PromptGenerationResponse:
    try:
        return generation_service.generate(request)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("", response_model=PromptSet, status_code=status.HTTP_201_CREATED)
def create_prompt_set(
    request: PromptSetUpsertRequest,
    catalog_service: CatalogService = Depends(get_catalog_service),
) -> PromptSet:
    try:
        return catalog_service.create_prompt_set(request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.put("/{prompt_set_id}", response_model=PromptSet)
def update_prompt_set(
    prompt_set_id: str,
    request: PromptSetUpsertRequest,
    catalog_service: CatalogService = Depends(get_catalog_service),
) -> PromptSet:
    try:
        return catalog_service.update_prompt_set(prompt_set_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt set not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/{prompt_set_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_prompt_set(
    prompt_set_id: str,
    catalog_service: CatalogService = Depends(get_catalog_service),
) -> None:
    try:
        catalog_service.delete_prompt_set(prompt_set_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt set not found.") from exc


@router.post("/{prompt_set_id}/recompute-similarity", response_model=PromptSet)
def recompute_similarity(
    prompt_set_id: str,
    catalog_service: CatalogService = Depends(get_catalog_service),
) -> PromptSet:
    try:
        return catalog_service.recompute_similarity(prompt_set_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt set not found.") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
