from __future__ import annotations

import math
from typing import Sequence

from openai import OpenAI

from app.core.config import settings
from app.schemas.prompt_sets import CatalogMetadata, PromptSet


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float | None:
    numerator = 0.0
    left_norm = 0.0
    right_norm = 0.0

    for left_value, right_value in zip(left, right):
        numerator += float(left_value) * float(right_value)
        left_norm += float(left_value) * float(left_value)
        right_norm += float(right_value) * float(right_value)

    denominator = math.sqrt(left_norm) * math.sqrt(right_norm)
    if denominator == 0.0:
        return None
    return numerator / denominator


class SimilarityService:
    def __init__(self) -> None:
        self._client: OpenAI | None = None

    def _client_or_raise(self) -> OpenAI:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for similarity calculation.")
        if self._client is None:
            self._client = OpenAI(api_key=settings.openai_api_key)
        return self._client

    def recompute_prompt_set(self, prompt_set: PromptSet) -> PromptSet:
        texts = [prompt_set.baseline.prompt] + [variation.prompt for variation in prompt_set.variations]
        client = self._client_or_raise()
        response = client.embeddings.create(
            model=settings.prompt_embedding_model,
            input=texts,
            encoding_format="float",
        )

        ordered_embeddings = [
            item.embedding for item in sorted(response.data, key=lambda item: item.index)
        ]
        baseline_embedding = ordered_embeddings[0]
        prompt_set.baseline.similarity_to_baseline = 1.0

        for variation, embedding in zip(prompt_set.variations, ordered_embeddings[1:]):
            variation.similarity_to_baseline = cosine_similarity(baseline_embedding, embedding)

        return prompt_set

    def catalog_metadata(self) -> CatalogMetadata:
        return CatalogMetadata(
            embedding_model=settings.prompt_embedding_model,
            similarity_metric="cosine_similarity",
        )

