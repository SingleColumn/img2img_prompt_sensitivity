from __future__ import annotations

from fastapi import APIRouter

from app.core.model_registry import MODELS
from app.core.paths import INPUT_IMAGES_DIR
from app.schemas.runtime import InputImageChoice, ModelChoice


router = APIRouter(prefix="/api", tags=["runtime"])


@router.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/models", response_model=list[ModelChoice])
def list_models() -> list[ModelChoice]:
    return [ModelChoice.model_validate(item) for item in MODELS]


@router.get("/input-images", response_model=list[InputImageChoice])
def list_input_images() -> list[InputImageChoice]:
    supported = {".png", ".jpg", ".jpeg", ".webp"}
    items: list[InputImageChoice] = []
    for path in sorted(INPUT_IMAGES_DIR.iterdir() if INPUT_IMAGES_DIR.exists() else []):
        if path.is_file() and path.suffix.lower() in supported:
            items.append(
                InputImageChoice(
                    file_name=path.name,
                    url=f"/static/input-images/{path.name}",
                )
            )
    return items

