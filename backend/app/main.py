from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.prompt_sets import router as prompt_sets_router
from app.api.runs import router as runs_router
from app.api.runtime import router as runtime_router
from app.core.paths import INPUT_IMAGES_DIR, OUTPUT_RUNS_DIR
from app.services.catalog_service import PromptCatalogError


app = FastAPI(title="img2img lab backend", version="0.1.0")


@app.exception_handler(PromptCatalogError)
async def prompt_catalog_error_handler(_request: Request, exc: PromptCatalogError) -> JSONResponse:
    # A corrupt or hand-broken prompt_sets.json should tell the user exactly what is
    # wrong, on any route, rather than surfacing as an opaque 500.
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": str(exc)},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(runtime_router)
app.include_router(prompt_sets_router)
app.include_router(runs_router)

app.mount("/static/input-images", StaticFiles(directory=INPUT_IMAGES_DIR), name="input-images")
app.mount("/static/output-runs", StaticFiles(directory=OUTPUT_RUNS_DIR), name="output-runs")
