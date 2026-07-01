from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    prompt_llm_model: str = os.getenv("PROMPT_LLM_MODEL", "gpt-5.5")
    prompt_embedding_model: str = os.getenv("PROMPT_EMBEDDING_MODEL", "text-embedding-3-large")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    fal_api_key: str | None = os.getenv("FAL_KEY")
    fal_result_timeout_seconds: int = int(os.getenv("FAL_RESULT_TIMEOUT_SECONDS", "600"))
    run_job_stall_timeout_seconds: int = int(os.getenv("RUN_JOB_STALL_TIMEOUT_SECONDS", "180"))


settings = Settings()
