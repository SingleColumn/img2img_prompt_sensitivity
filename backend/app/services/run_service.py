from __future__ import annotations

import html
import json
import time
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.model_registry import MODELS
from app.core.paths import INPUT_IMAGES_DIR, OUTPUT_RUNS_DIR
from app.schemas.prompt_sets import PromptSet, is_equivalent_variation_name
from app.schemas.runs import (
    ProgressUpdate,
    RunCreateRequest,
    RunIndex,
    RunItem,
    RunModelInfo,
    RunPromptInfo,
    RunSummary,
)
from app.services.catalog_service import CatalogService
from app.services.image_generation_service import ImageGenerationService


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")


def timestamp_for_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%MZ")


def sanitize_for_filename(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip())
    return normalized.strip("-") or "item"


class RunService:
    def __init__(
        self,
        catalog_service: CatalogService,
        image_generation_service: ImageGenerationService,
    ) -> None:
        self._catalog_service = catalog_service
        self._image_generation_service = image_generation_service
        OUTPUT_RUNS_DIR.mkdir(parents=True, exist_ok=True)

    def create_run(
        self,
        request: RunCreateRequest,
        progress_callback: Any = None,
    ) -> RunIndex:
        if request.execution_mode not in {"mock", "provider"}:
            raise ValueError("execution_mode must be either 'mock' or 'provider'.")

        prompt_set = self._catalog_service.get_prompt_set(request.prompt_set_id)
        if prompt_set is None:
            raise KeyError(f"Prompt set '{request.prompt_set_id}' was not found.")

        input_image_path = INPUT_IMAGES_DIR / request.input_image
        if not input_image_path.exists():
            raise FileNotFoundError(f"Input image '{request.input_image}' was not found.")

        selected_models = self._resolve_models(request.model_ids)
        prompts = self._expand_prompts(prompt_set)
        prompts = self._filter_prompts(prompts, request.prompt_keys)
        run_id = self._ensure_unique_run_id(prompt_set.prompt_set, selected_models)
        run_dir = OUTPUT_RUNS_DIR / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        generated_at = utc_now_iso()
        total_steps = len(selected_models) * len(prompts)
        completed_steps = 0

        items: list[RunItem] = []
        for model in selected_models:
            for prompt in prompts:
                step_started = time.perf_counter()
                completed_steps += 1
                progress_message = (
                    f"[{completed_steps}/{total_steps}] {request.execution_mode} | "
                    f"{model['display_name']} | {prompt.key}"
                )
                print(progress_message)
                if progress_callback is not None:
                    progress_callback(
                        ProgressUpdate(
                            completed_steps=completed_steps - 1,
                            total_steps=total_steps,
                            current_model_id=model["id"],
                            current_prompt_key=prompt.key,
                            message=f"Running {model['display_name']} / {prompt.key}",
                        )
                    )
                file_name = (
                    self._build_output_filename(
                        model=model,
                        prompt_key=prompt.key,
                        execution_mode=request.execution_mode,
                    )
                )
                request_payload: dict[str, Any] | None = None
                raw_response: dict[str, Any] | None = None
                generation_elapsed_s: float | None = None
                provider_elapsed_s: float | None = None
                download_elapsed_s: float | None = None

                if request.execution_mode == "mock":
                    self._write_placeholder_image(
                        destination=run_dir / file_name,
                        run_id=run_id,
                        model_name=model["display_name"],
                        prompt_label=prompt.label,
                        prompt_kind=prompt.prompt_kind,
                        prompt_text=prompt.prompt,
                    )
                else:
                    generated = self._image_generation_service.generate(model, input_image_path, prompt.prompt)
                    file_name = (
                        f"{sanitize_for_filename(model['id'])}_{sanitize_for_filename(prompt.key)}."
                        f"{generated['extension']}"
                    )
                    (run_dir / file_name).write_bytes(generated["image_bytes"])
                    generation_elapsed_s = generated.get("generation_elapsed_s")
                    provider_elapsed_s = generated.get("provider_elapsed_s")
                    download_elapsed_s = generated.get("download_elapsed_s")
                    request_payload = generated.get("request_payload")
                    raw_response = generated.get("raw_response")

                items.append(
                    RunItem(
                        model_id=model["id"],
                        model_display_name=model["display_name"],
                        prompt_key=prompt.key,
                        prompt_label=prompt.label,
                        prompt_kind=prompt.prompt_kind,
                        variation_type=prompt.variation_type,
                        similarity_to_baseline=prompt.similarity_to_baseline,
                        prompt_text=prompt.prompt,
                        output_file=file_name,
                        image_path=file_name,
                        timestamp=generated_at,
                        generation_elapsed_s=generation_elapsed_s,
                        provider_elapsed_s=provider_elapsed_s,
                        download_elapsed_s=download_elapsed_s,
                        request_payload=request_payload,
                        raw_response=raw_response,
                    )
                )
                elapsed_seconds = time.perf_counter() - step_started
                print(
                    f"Completed {model['display_name']} | {prompt.key} "
                    f"in {elapsed_seconds:.2f}s -> {file_name}"
                    + (
                        f" (provider={provider_elapsed_s:.2f}s, download={download_elapsed_s:.2f}s)"
                        if provider_elapsed_s is not None and download_elapsed_s is not None
                        else ""
                    )
                )
                if progress_callback is not None:
                    progress_callback(
                        ProgressUpdate(
                            completed_steps=completed_steps,
                            total_steps=total_steps,
                            current_model_id=model["id"],
                            current_prompt_key=prompt.key,
                            message=(
                                f"Completed {model['display_name']} / {prompt.key} "
                                f"in {elapsed_seconds:.2f}s"
                            ),
                        )
                    )

        run_index = RunIndex(
            run_id=run_id,
            generated_at=generated_at,
            prompt_set_id=prompt_set.prompt_set,
            input_image=request.input_image,
            execution_mode=request.execution_mode,
            selected_models=[
                RunModelInfo(id=model["id"], display_name=model["display_name"])
                for model in selected_models
            ],
            prompts=prompts,
            items=items,
        )

        self._write_json(run_dir / "manifest.json", run_index.model_dump(mode="json"))
        self._write_json(run_dir / "index.json", run_index.model_dump(mode="json"))
        return run_index

    def list_runs(self) -> list[RunSummary]:
        runs: list[RunSummary] = []
        if not OUTPUT_RUNS_DIR.exists():
            return runs

        for run_dir in sorted((path for path in OUTPUT_RUNS_DIR.iterdir() if path.is_dir()), reverse=True):
            index_path = run_dir / "index.json"
            if not index_path.exists():
                continue
            payload = json.loads(index_path.read_text(encoding="utf-8"))
            run_index = RunIndex.model_validate(payload)
            runs.append(
                RunSummary(
                    run_id=run_index.run_id,
                    generated_at=run_index.generated_at,
                    prompt_set_id=run_index.prompt_set_id,
                    input_image=run_index.input_image,
                    execution_mode=run_index.execution_mode,
                    model_count=len(run_index.selected_models),
                    prompt_count=len(run_index.prompts),
                    avg_generation_elapsed_s=(
                        sum(
                            item.generation_elapsed_s or 0.0
                            for item in run_index.items
                            if item.generation_elapsed_s is not None
                        )
                        / max(
                            1,
                            len([item for item in run_index.items if item.generation_elapsed_s is not None]),
                        )
                        if any(item.generation_elapsed_s is not None for item in run_index.items)
                        else None
                    ),
                )
            )
        return runs

    def get_run(self, run_id: str) -> RunIndex | None:
        index_path = OUTPUT_RUNS_DIR / run_id / "index.json"
        if not index_path.exists():
            return None
        payload = json.loads(index_path.read_text(encoding="utf-8"))
        return RunIndex.model_validate(payload)

    def delete_run(self, run_id: str) -> None:
        run_dir = OUTPUT_RUNS_DIR / run_id
        index_path = run_dir / "index.json"
        if not run_dir.is_dir() or not index_path.exists():
            raise KeyError(run_id)
        shutil.rmtree(run_dir)

    def _resolve_models(self, model_ids: list[str]) -> list[dict[str, Any]]:
        models_by_id = {model["id"]: model for model in MODELS}
        selected: list[dict[str, Any]] = []
        for model_id in model_ids:
            model = models_by_id.get(model_id)
            if model is None:
                raise ValueError(f"Unsupported model id '{model_id}'.")
            selected.append(model)
        return selected

    def _expand_prompts(self, prompt_set: PromptSet) -> list[RunPromptInfo]:
        prompts = [
            RunPromptInfo(
                key="baseline",
                label="Baseline",
                prompt=prompt_set.baseline.prompt,
                prompt_kind="baseline",
                similarity_to_baseline=1.0,
            )
        ]

        equivalent = next(
            (
                variation
                for variation in prompt_set.variations
                if is_equivalent_variation_name(variation.variation_name)
            ),
            None,
        )
        non_equivalent = [
            variation
            for variation in prompt_set.variations
            if not is_equivalent_variation_name(variation.variation_name)
        ]

        if equivalent is not None:
            prompts.append(
                RunPromptInfo(
                    key="equivalent",
                    label="Equivalent",
                    prompt=equivalent.prompt,
                    prompt_kind="equivalent",
                    variation_type=equivalent.variation_type,
                    similarity_to_baseline=equivalent.similarity_to_baseline,
                )
            )

        for variation in non_equivalent:
            prompts.append(
                RunPromptInfo(
                    key=variation.variation_name,
                    label=variation.variation_name,
                    prompt=variation.prompt,
                    prompt_kind="variation",
                    variation_type=variation.variation_type,
                    similarity_to_baseline=variation.similarity_to_baseline,
                )
            )
        return prompts

    def _filter_prompts(
        self,
        prompts: list[RunPromptInfo],
        selected_prompt_keys: list[str],
    ) -> list[RunPromptInfo]:
        if not selected_prompt_keys:
            return prompts

        available = {prompt.key for prompt in prompts}
        unknown = [key for key in selected_prompt_keys if key not in available]
        if unknown:
            raise ValueError(f"Unknown prompt key selection: {', '.join(unknown)}")

        selected = set(selected_prompt_keys)
        filtered = [prompt for prompt in prompts if prompt.key in selected]
        if not filtered:
            raise ValueError("At least one prompt must be selected for a run.")
        return filtered

    def _build_output_filename(
        self,
        model: dict[str, Any],
        prompt_key: str,
        execution_mode: str,
    ) -> str:
        extension = "svg" if execution_mode == "mock" else "png"
        return f"{sanitize_for_filename(model['id'])}_{sanitize_for_filename(prompt_key)}.{extension}"

    def _ensure_unique_run_id(self, prompt_set_id: str, selected_models: list[dict[str, Any]]) -> str:
        base = (
            f"{timestamp_for_run_id()}_"
            f"{sanitize_for_filename(prompt_set_id)}_"
            f"{self._summarize_models_for_run_id(selected_models)}"
        )
        candidate = base
        suffix = 2
        while (OUTPUT_RUNS_DIR / candidate).exists():
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate

    def _summarize_models_for_run_id(self, selected_models: list[dict[str, Any]]) -> str:
        if not selected_models:
            return "no-model"
        first_model = sanitize_for_filename(selected_models[0]["display_name"])
        extra_count = len(selected_models) - 1
        if extra_count <= 0:
            return first_model
        return f"{first_model}-plus-{extra_count}"

    def _write_json(self, path: Path, payload: dict) -> None:
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def _write_placeholder_image(
        self,
        destination: Path,
        run_id: str,
        model_name: str,
        prompt_label: str,
        prompt_kind: str,
        prompt_text: str,
    ) -> None:
        safe_model_name = html.escape(model_name)
        safe_prompt_label = html.escape(prompt_label)
        safe_prompt_kind = html.escape(prompt_kind)
        safe_run_id = html.escape(run_id)
        safe_prompt_text = html.escape(prompt_text)

        wrapped_lines = self._wrap_text(safe_prompt_text, 52)[:7]
        text_rows = "".join(
            f'<text x="48" y="{190 + (index * 32)}" class="body">{line}</text>'
            for index, line in enumerate(wrapped_lines)
        )

        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#1f2c3f"/>
      <stop offset="55%" stop-color="#8f4e32"/>
      <stop offset="100%" stop-color="#f1d7a5"/>
    </linearGradient>
  </defs>
  <rect width="1024" height="1024" fill="url(#bg)"/>
  <rect x="36" y="36" width="952" height="952" rx="28" fill="#fff8ee" fill-opacity="0.82" />
  <text x="48" y="96" class="eyebrow">MOCK RUN OUTPUT</text>
  <text x="48" y="146" class="headline">{safe_prompt_label}</text>
  <text x="48" y="176" class="meta">{safe_prompt_kind} | {safe_model_name}</text>
  {text_rows}
  <text x="48" y="924" class="footer">{safe_run_id}</text>
  <style>
    .eyebrow {{
      font: 700 28px Georgia, serif;
      letter-spacing: 0.16em;
      fill: #9d5428;
    }}
    .headline {{
      font: 700 54px Georgia, serif;
      fill: #23180f;
    }}
    .meta {{
      font: 400 28px Georgia, serif;
      fill: #5b4637;
    }}
    .body {{
      font: 400 28px Georgia, serif;
      fill: #2f251d;
    }}
    .footer {{
      font: 400 24px Georgia, serif;
      fill: #5b4637;
    }}
  </style>
</svg>"""
        destination.write_text(svg, encoding="utf-8")

    def _wrap_text(self, text: str, max_line_length: int) -> list[str]:
        words = text.split()
        if not words:
            return [""]

        lines: list[str] = []
        current: list[str] = []
        current_length = 0
        for word in words:
            projected = len(word) if not current else current_length + 1 + len(word)
            if projected > max_line_length:
                lines.append(" ".join(current))
                current = [word]
                current_length = len(word)
            else:
                current.append(word)
                current_length = projected
        if current:
            lines.append(" ".join(current))
        return lines
