from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


def _validate_non_empty(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("Value must be a non-empty string.")
    return normalized


class RunCreateRequest(BaseModel):
    prompt_set_id: str
    input_image: str
    model_ids: list[str] = Field(min_length=1)
    prompt_keys: list[str] = Field(default_factory=list)
    execution_mode: str = "mock"

    _normalize_prompt_set_id = field_validator("prompt_set_id")(_validate_non_empty)
    _normalize_input_image = field_validator("input_image")(_validate_non_empty)


class RunModelInfo(BaseModel):
    id: str
    display_name: str


class RunPromptInfo(BaseModel):
    key: str
    label: str
    prompt: str
    prompt_kind: str
    variation_type: str | None = None
    similarity_to_baseline: float | None = None


class RunItem(BaseModel):
    model_id: str
    model_display_name: str
    prompt_key: str
    prompt_label: str
    prompt_kind: str
    variation_type: str | None = None
    similarity_to_baseline: float | None = None
    prompt_text: str
    output_file: str
    image_path: str
    timestamp: str
    generation_elapsed_s: float | None = None
    provider_elapsed_s: float | None = None
    download_elapsed_s: float | None = None
    request_payload: dict | None = None
    raw_response: dict | None = None


class RunIndex(BaseModel):
    run_id: str
    generated_at: str
    prompt_set_id: str
    input_image: str
    execution_mode: str
    selected_models: list[RunModelInfo]
    prompts: list[RunPromptInfo]
    items: list[RunItem]


class RunSummary(BaseModel):
    run_id: str
    generated_at: str
    prompt_set_id: str
    input_image: str
    execution_mode: str
    model_count: int
    prompt_count: int
    avg_generation_elapsed_s: float | None = None


class RunJob(BaseModel):
    job_id: str
    status: Literal["queued", "running", "stalled", "completed", "failed"]
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    last_updated_at: str | None = None
    step_started_at: str | None = None
    stall_timeout_s: int | None = None
    execution_mode: str
    prompt_set_id: str
    input_image: str
    model_ids: list[str]
    prompt_keys: list[str]
    completed_steps: int = 0
    total_steps: int = 0
    current_model_id: str | None = None
    current_prompt_key: str | None = None
    message: str = ""
    run_id: str | None = None
    error: str | None = None


class ProgressUpdate(BaseModel):
    completed_steps: int
    total_steps: int
    current_model_id: str | None
    current_prompt_key: str | None
    message: str
