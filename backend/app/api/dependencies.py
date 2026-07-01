from __future__ import annotations

from functools import lru_cache

from app.services.catalog_service import CatalogService
from app.services.image_generation_service import ImageGenerationService
from app.services.prompt_generation_service import PromptGenerationService
from app.services.run_job_service import RunJobService
from app.services.run_service import RunService
from app.services.similarity_service import SimilarityService


@lru_cache(maxsize=1)
def get_similarity_service() -> SimilarityService:
    return SimilarityService()


@lru_cache(maxsize=1)
def get_catalog_service() -> CatalogService:
    return CatalogService(get_similarity_service())


@lru_cache(maxsize=1)
def get_prompt_generation_service() -> PromptGenerationService:
    return PromptGenerationService(get_similarity_service())


@lru_cache(maxsize=1)
def get_image_generation_service() -> ImageGenerationService:
    return ImageGenerationService()


@lru_cache(maxsize=1)
def get_run_service() -> RunService:
    return RunService(get_catalog_service(), get_image_generation_service())


@lru_cache(maxsize=1)
def get_run_job_service() -> RunJobService:
    return RunJobService(get_run_service())
