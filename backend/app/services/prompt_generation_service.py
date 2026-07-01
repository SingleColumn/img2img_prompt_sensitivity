from __future__ import annotations

import json
from textwrap import dedent

from openai import OpenAI

from app.core.config import settings
from app.schemas.prompt_sets import (
    BaselinePrompt,
    PromptGenerationMetadata,
    PromptGenerationRequest,
    PromptGenerationResponse,
    PromptSet,
    PromptVariation,
)
from app.services.similarity_service import SimilarityService


PROMPT_TEMPLATE_VERSION = "v1"


class PromptGenerationService:
    def __init__(self, similarity_service: SimilarityService) -> None:
        self._similarity_service = similarity_service
        self._client: OpenAI | None = None

    def _client_or_raise(self) -> OpenAI:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for prompt generation.")
        if self._client is None:
            self._client = OpenAI(api_key=settings.openai_api_key)
        return self._client

    def generate(self, request: PromptGenerationRequest) -> PromptGenerationResponse:
        client = self._client_or_raise()
        response = client.responses.create(
            model=settings.prompt_llm_model,
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": self._system_prompt(),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": self._user_prompt(request),
                        }
                    ],
                },
            ],
        )

        output_text = getattr(response, "output_text", None)
        if not output_text:
            raise RuntimeError("Prompt generation response did not contain output_text.")

        generated = self._parse_generated_payload(output_text, request.include_equivalent, request.variation_count)
        prompt_set = PromptSet(
            prompt_set=request.prompt_set,
            baseline=BaselinePrompt(prompt=request.baseline_prompt, similarity_to_baseline=1.0),
            variations=generated,
        )
        prompt_set = self._similarity_service.recompute_prompt_set(prompt_set)

        return PromptGenerationResponse(
            prompt_set=prompt_set,
            generation_metadata=PromptGenerationMetadata(
                llm_model=settings.prompt_llm_model,
                template_version=PROMPT_TEMPLATE_VERSION,
            ),
        )

    def _system_prompt(self) -> str:
        return dedent(
            """
            You rewrite image-edit prompts without changing their intended result.
            Preserve the exact semantic intent of the baseline prompt.
            Return valid JSON only.

            Output format:
            {
              "equivalent": {
                "prompt": "...",
                "variation_type": "Word order"
              },
              "variations": [
                {
                  "variation_name": "Variant 1",
                  "variation_type": "Synonym substitution",
                  "prompt": "..."
                }
              ]
            }

            Rules:
            - The equivalent prompt must keep the same meaning and only rearrange phrasing.
            - Variations must preserve the intended image edit outcome.
            - Variations may use synonyms or close paraphrases but must not introduce new visual goals.
            - Do not include explanations, markdown, or extra keys.
            """
        ).strip()

    def _user_prompt(self, request: PromptGenerationRequest) -> str:
        equivalent_instruction = "yes" if request.include_equivalent else "no"
        return dedent(
            f"""
            Prompt set name: {request.prompt_set}
            Baseline prompt: {request.baseline_prompt}
            Generate equivalent prompt: {equivalent_instruction}
            Number of non-equivalent variations: {request.variation_count}
            """
        ).strip()

    def _parse_generated_payload(
        self,
        output_text: str,
        include_equivalent: bool,
        variation_count: int,
    ) -> list[PromptVariation]:
        try:
            payload = json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Prompt generation returned invalid JSON.") from exc

        variations: list[PromptVariation] = []

        if include_equivalent:
            equivalent = payload.get("equivalent")
            if not isinstance(equivalent, dict):
                raise RuntimeError("Prompt generation did not return the required equivalent prompt.")
            variations.append(
                PromptVariation(
                    variation_name="Equivalent",
                    variation_type=str(equivalent.get("variation_type", "Word order")),
                    prompt=str(equivalent.get("prompt", "")),
                )
            )

        raw_variations = payload.get("variations", [])
        if not isinstance(raw_variations, list):
            raise RuntimeError("Prompt generation variations field must be a list.")

        for index, item in enumerate(raw_variations[:variation_count], start=1):
            if not isinstance(item, dict):
                raise RuntimeError("Prompt generation included an invalid variation item.")
            variations.append(
                PromptVariation(
                    variation_name=str(item.get("variation_name") or f"Variant {index}"),
                    variation_type=str(item.get("variation_type") or "Synonym substitution"),
                    prompt=str(item.get("prompt", "")),
                )
            )

        if len(raw_variations) < variation_count:
            raise RuntimeError("Prompt generation returned fewer variations than requested.")

        return variations
