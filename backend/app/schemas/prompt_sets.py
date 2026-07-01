from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _validate_non_empty(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("Value must be a non-empty string.")
    return normalized


def normalize_variation_name(value: str) -> str:
    return " ".join(value.strip().replace("_", " ").replace("-", " ").lower().split())


def is_equivalent_variation_name(value: str) -> bool:
    return normalize_variation_name(value) == "equivalent"


class CatalogMetadata(BaseModel):
    embedding_model: str = "text-embedding-3-large"
    similarity_metric: str = "cosine_similarity"
    description: str = "Prompt sensitivity benchmark for image-to-image generation"


class BaselinePrompt(BaseModel):
    prompt: str
    similarity_to_baseline: float = 1.0

    _normalize_prompt = field_validator("prompt")(_validate_non_empty)


class PromptVariation(BaseModel):
    variation_name: str
    variation_type: str
    prompt: str
    similarity_to_baseline: float | None = None

    _normalize_name = field_validator("variation_name")(_validate_non_empty)
    _normalize_type = field_validator("variation_type")(_validate_non_empty)
    _normalize_prompt = field_validator("prompt")(_validate_non_empty)


class PromptSet(BaseModel):
    prompt_set: str
    baseline: BaselinePrompt
    variations: list[PromptVariation] = Field(default_factory=list)

    _normalize_id = field_validator("prompt_set")(_validate_non_empty)

    @model_validator(mode="after")
    def validate_variations(self) -> "PromptSet":
        names = [variation.variation_name for variation in self.variations]
        if len(set(names)) != len(names):
            raise ValueError("Variation names must be unique within a prompt set.")

        equivalent_count = sum(1 for name in names if is_equivalent_variation_name(name))
        if equivalent_count > 1:
            raise ValueError("A prompt set may contain at most one 'equivalent' variation.")

        return self


class PromptSetCatalog(BaseModel):
    metadata: CatalogMetadata = Field(default_factory=CatalogMetadata)
    prompt_sets: list[PromptSet] = Field(default_factory=list)


class PromptSetSummary(BaseModel):
    prompt_set: str
    baseline_prompt: str
    variation_count: int
    has_equivalent: bool


class PromptGenerationRequest(BaseModel):
    prompt_set: str
    baseline_prompt: str
    include_equivalent: bool = True
    variation_count: int = Field(default=2, ge=0, le=10)

    _normalize_id = field_validator("prompt_set")(_validate_non_empty)
    _normalize_prompt = field_validator("baseline_prompt")(_validate_non_empty)


class PromptSetUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_set: str
    baseline: BaselinePrompt
    variations: list[PromptVariation] = Field(default_factory=list)


class PromptGenerationMetadata(BaseModel):
    llm_provider: Literal["openai"] = "openai"
    llm_model: str
    template_version: str = "v1"


class PromptGenerationResponse(BaseModel):
    prompt_set: PromptSet
    generation_metadata: PromptGenerationMetadata
