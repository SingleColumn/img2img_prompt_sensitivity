from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.core.paths import PROMPT_SETS_FILE, PROMPT_SETS_DIR
from app.schemas.prompt_sets import (
    CatalogMetadata,
    PromptSet,
    PromptSetCatalog,
    PromptSetSummary,
    PromptSetUpsertRequest,
    is_equivalent_variation_name,
)
from app.services.similarity_service import SimilarityService


class PromptCatalogError(Exception):
    """The prompt-set catalog file exists but cannot be read or does not match the schema.

    Carries a human-readable message intended to be shown directly to someone who may
    have hand-edited ``prompt_sets.json`` — it points at what is wrong rather than
    silently repairing the file.
    """


class CatalogService:
    def __init__(self, similarity_service: SimilarityService) -> None:
        self._similarity_service = similarity_service
        PROMPT_SETS_DIR.mkdir(parents=True, exist_ok=True)

    def load_catalog(self) -> PromptSetCatalog:
        if not PROMPT_SETS_FILE.exists():
            return PromptSetCatalog(
                metadata=self._similarity_service.catalog_metadata(),
                prompt_sets=[],
            )

        raw_text = PROMPT_SETS_FILE.read_text(encoding="utf-8")

        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise PromptCatalogError(
                f"{PROMPT_SETS_FILE.name} is not valid JSON "
                f"(line {exc.lineno}, column {exc.colno}): {exc.msg}."
            ) from exc

        try:
            return PromptSetCatalog.model_validate(payload)
        except ValidationError as exc:
            raise PromptCatalogError(
                f"{PROMPT_SETS_FILE.name} does not match the prompt-set schema. "
                f"{self._summarize_validation_error(exc)}"
            ) from exc

    def list_prompt_sets(self) -> list[PromptSetSummary]:
        catalog = self.load_catalog()
        return [
            PromptSetSummary(
                prompt_set=entry.prompt_set,
                baseline_prompt=entry.baseline.prompt,
                variation_count=len(entry.variations),
                has_equivalent=any(
                    is_equivalent_variation_name(item.variation_name) for item in entry.variations
                ),
            )
            for entry in catalog.prompt_sets
        ]

    def get_prompt_set(self, prompt_set_id: str) -> PromptSet | None:
        catalog = self.load_catalog()
        for entry in catalog.prompt_sets:
            if entry.prompt_set == prompt_set_id:
                return entry
        return None

    def create_prompt_set(self, request: PromptSetUpsertRequest) -> PromptSet:
        catalog = self.load_catalog()
        self._ensure_unique_prompt_set(catalog, request.prompt_set)
        prompt_set = PromptSet.model_validate(request.model_dump())
        prompt_set = self._similarity_service.recompute_prompt_set(prompt_set)
        catalog.prompt_sets.append(prompt_set)
        catalog.metadata = self._metadata_for_write(catalog.metadata)
        self._write_catalog(catalog)
        return prompt_set

    def update_prompt_set(self, prompt_set_id: str, request: PromptSetUpsertRequest) -> PromptSet:
        catalog = self.load_catalog()
        index = self._find_prompt_set_index(catalog, prompt_set_id)
        if index is None:
            raise KeyError(prompt_set_id)
        if request.prompt_set != prompt_set_id:
            self._ensure_unique_prompt_set(catalog, request.prompt_set, exclude_id=prompt_set_id)

        prompt_set = PromptSet.model_validate(request.model_dump())
        prompt_set = self._similarity_service.recompute_prompt_set(prompt_set)
        catalog.prompt_sets[index] = prompt_set
        catalog.metadata = self._metadata_for_write(catalog.metadata)
        self._write_catalog(catalog)
        return prompt_set

    def recompute_similarity(self, prompt_set_id: str) -> PromptSet:
        catalog = self.load_catalog()
        index = self._find_prompt_set_index(catalog, prompt_set_id)
        if index is None:
            raise KeyError(prompt_set_id)
        recomputed = self._similarity_service.recompute_prompt_set(catalog.prompt_sets[index])
        catalog.prompt_sets[index] = recomputed
        catalog.metadata = self._metadata_for_write(catalog.metadata)
        self._write_catalog(catalog)
        return recomputed

    def delete_prompt_set(self, prompt_set_id: str) -> None:
        catalog = self.load_catalog()
        index = self._find_prompt_set_index(catalog, prompt_set_id)
        if index is None:
            raise KeyError(prompt_set_id)
        del catalog.prompt_sets[index]
        catalog.metadata = self._metadata_for_write(catalog.metadata)
        self._write_catalog(catalog)

    def _metadata_for_write(self, current: CatalogMetadata) -> CatalogMetadata:
        updated = self._similarity_service.catalog_metadata()
        if current.description:
            updated.description = current.description
        return updated

    def _find_prompt_set_index(self, catalog: PromptSetCatalog, prompt_set_id: str) -> int | None:
        for index, entry in enumerate(catalog.prompt_sets):
            if entry.prompt_set == prompt_set_id:
                return index
        return None

    def _ensure_unique_prompt_set(
        self,
        catalog: PromptSetCatalog,
        prompt_set_id: str,
        exclude_id: str | None = None,
    ) -> None:
        for entry in catalog.prompt_sets:
            if entry.prompt_set == prompt_set_id and entry.prompt_set != exclude_id:
                raise ValueError(f"Prompt set '{prompt_set_id}' already exists.")

    def _write_catalog(self, catalog: PromptSetCatalog) -> None:
        # The on-disk format is exactly PromptSetCatalog.model_dump() — no translation
        # layer. Write to a temp file and atomically replace so a crash mid-write can
        # never leave a half-written catalog.
        temp_path = Path(f"{PROMPT_SETS_FILE}.tmp")
        temp_path.write_text(
            json.dumps(catalog.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temp_path.replace(PROMPT_SETS_FILE)

    def _summarize_validation_error(self, exc: ValidationError) -> str:
        parts: list[str] = []
        for error in exc.errors():
            location = ".".join(str(item) for item in error.get("loc", ())) or "(root)"
            parts.append(f"{location}: {error.get('msg', 'invalid value')}")
        return "; ".join(parts) or str(exc)
