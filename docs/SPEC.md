# img2img lab — Specification

**Status: as built.** This document describes the application as it actually exists in this repository, not a forward-looking proposal. Where the implementation diverged from the original greenfield proposal, this document reflects the implementation. The original pre-build vision is preserved in `legacy/GREENFIELD_SPEC.md` for historical reference.

---

## 1. Purpose

A local-only web app for studying **prompt sensitivity in image-to-image generation**: how a model's output changes when a prompt's wording changes but its intent does not.

The app runs as two local processes — a Python/FastAPI backend and a React/TypeScript frontend — with local-filesystem persistence and provider API keys read from the machine environment. There is no cloud deployment, authentication, multi-user support, remote database, or background-queue infrastructure.

## 2. Product workflow

One continuous flow:

1. Create or select a prompt set.
2. Generate an `equivalent` and N variation prompts from a baseline prompt (LLM-backed).
3. Revise, regenerate, and recompute similarity until satisfied.
4. Save the prompt set locally.
5. Select one input image and one or more image-edit models.
6. Run image generation (mock or via provider APIs).
7. Inspect outputs in a comparison view.

## 3. Architecture

Two local processes:

- **Backend** (`http://127.0.0.1:8000`) — owns all environment variables, file I/O, and provider calls. Reads/writes prompt-set files, reads input images, calls OpenAI and FAL, writes output images and run metadata.
- **Frontend** (`http://localhost:5173`) — prompt authoring, prompt review/regeneration, model+image selection, run progress, and result comparison.

**Core constraint:** the frontend never calls provider APIs directly. API keys stay server-side, filesystem operations stay on the backend, provider integration stays centralized. The frontend talks only to the local backend (API base `http://127.0.0.1:8000/api`; static assets under `http://127.0.0.1:8000/static/...`).

**CORS / port constraint:** the backend allows origins `http://localhost:5173` and `http://127.0.0.1:5173` only. The frontend dev server is pinned to port 5173 with `strictPort: true`, so it fails to start (with a clear error) if 5173 is occupied rather than drifting to another port and breaking all API calls via CORS. If the port is ever changed, `frontend/vite.config.ts` and the backend `allow_origins` list must be updated together.

## 4. Technology stack

- **Backend:** Python 3.12+ (developed on 3.13), FastAPI, Uvicorn, Pydantic v2, python-dotenv, openai, fal-client, requests.
- **Frontend:** React 18, TypeScript, Vite 5 (`@vitejs/plugin-react`). No state or component libraries.
- **Storage:** local JSON for metadata, local filesystem for images.

## 5. Project layout

The app lives at the repository root (there is no wrapper directory):

```text
backend/
  app/
    api/        prompt_sets.py, runs.py, runtime.py, dependencies.py
    core/       paths.py, config.py, model_registry.py
    services/   catalog_service.py, similarity_service.py, run_service.py, run_job_service.py
    schemas/    prompt_sets.py, runs.py, runtime.py
    main.py
  tests/
  requirements.txt
frontend/
  src/
    api/client.ts
    styles/
    App.tsx, main.tsx
  package.json, tsconfig*.json, vite.config.ts
data/
  prompt_sets/prompt_sets.json
  input_images/
  output_runs/
docs/
  SPEC.md, DESIGN.md
```

**Path anchoring:** `backend/app/core/paths.py` derives `APP_ROOT` as `Path(__file__).resolve().parents[3]`, which resolves to the repository root. All data paths (`DATA_DIR`, `PROMPT_SETS_DIR`, `PROMPT_SETS_FILE`, `INPUT_IMAGES_DIR`, `OUTPUT_RUNS_DIR`) derive from it. Do not change the `parents[3]` depth.

## 6. Data model

### 6.1 Prompt-set catalog

The single source of truth is `data/prompt_sets/prompt_sets.json`.

**The on-disk format is exactly the Pydantic schema** — there is no translation layer. The file is `PromptSetCatalog.model_dump()`: a top-level object with `metadata` and `prompt_sets`. Loading is `PromptSetCatalog.model_validate(json.loads(text))`; saving is `json.dumps(catalog.model_dump())` written atomically (temp file + `replace`).

```json
{
  "metadata": {
    "embedding_model": "text-embedding-3-large",
    "similarity_metric": "cosine_similarity",
    "description": "Prompt sensitivity benchmark for image-to-image generation"
  },
  "prompt_sets": [
    {
      "prompt_set": "identity_pixel_art",
      "baseline": {
        "prompt": "Create a pixelated version of this image with blue, yellow, green and golden hues while keeping the person recognisable.",
        "similarity_to_baseline": 1.0
      },
      "variations": [
        {
          "variation_name": "equivalent",
          "variation_type": "word_order",
          "prompt": "While keeping the person recognisable, create a pixelated version of this image with blue, yellow, green and golden hues.",
          "similarity_to_baseline": 0.98
        },
        {
          "variation_name": "variant_1",
          "variation_type": "synonym_substitution",
          "prompt": "Create a pixelated version of this image with blue, yellow, green and golden hues while preserving the person's appearance.",
          "similarity_to_baseline": 0.95
        }
      ]
    }
  ]
}
```

The Pydantic models (`schemas/prompt_sets.py`) are `PromptSetCatalog { metadata: CatalogMetadata, prompt_sets: PromptSet[] }`, where each `PromptSet` has `prompt_set` (the identifier), `baseline: BaselinePrompt { prompt, similarity_to_baseline=1.0 }`, and `variations: PromptVariation[] { variation_name, variation_type, prompt, similarity_to_baseline }`.

**Hand-editing.** The file is plain, human-editable JSON and may be edited directly. On read, an invalid file is **not** silently repaired — it raises a clear error that names the problem and is surfaced to the caller as HTTP 422 (e.g. `prompt_sets.json is not valid JSON (line 5, column 3): ...` for a syntax error, or `prompt_sets.0.baseline: Field required` for a schema violation). This leaves the user's file untouched until they fix it, rather than rewriting it. (Editing in the UI is the primary path and always writes valid JSON.)

### 6.2 Prompt semantics and rules

- `prompt_set` / `prompt_set_id` is the stable identifier.
- `baseline` is user-authored and is the semantic reference point; its `similarity_to_baseline` is always `1.0`.
- The `equivalent` variation rearranges the baseline with the same meaning.
- Other variations preserve intent but change wording (synonyms, paraphrase, broadening, style shift).

Validation (enforced by Pydantic):
- exactly one baseline;
- at most one variation named `equivalent`;
- variation names unique within a set;
- all prompt strings non-empty (trimmed).

### 6.3 Similarity calculation

Computed by the backend, never authored in the UI (`SimilarityService`):
- embedding model: `PROMPT_EMBEDDING_MODEL` (default `text-embedding-3-large`);
- metric: cosine similarity;
- baseline fixed at `1.0`; each variation scored against the baseline embedding of the same set.

On create, update, or explicit recompute, the backend validates the set, recomputes embeddings for baseline + all variations, updates every `similarity_to_baseline`, and writes atomically. **Requires `OPENAI_API_KEY`** — without it, save/update/recompute raise an error (HTTP 4xx), and nothing is written.

### 6.4 Prompt generation

The backend owns a versioned prompt-generation template (in code, not the UI). Default rewrite model `PROMPT_LLM_MODEL` = `gpt-5.5`. The LLM is instructed to preserve intent, avoid changing the requested edit, produce one reorder-only `equivalent`, produce the requested number of wording-substitution variations, and return strict JSON. The backend normalizes output into the canonical schema and scores similarity. Generation does **not** persist — it returns prompts for review; saving is a separate step.

## 7. Run model

A run = one prompt set × one input image × one or more models, generating outputs for the baseline and every selected prompt in the set.

### 7.1 Execution modes

- **`provider`** — real calls to OpenAI / FAL; writes real image outputs. Requires the relevant key (`OPENAI_API_KEY` / `FAL_KEY`). This is the only mode exposed in the UI.
- **`mock`** — no provider calls; writes placeholder SVG outputs. Available via the API directly (useful for testing the run pipeline without spending credits); not exposed in the UI.

Execution is **sequential** in v1.

### 7.2 Run request

`RunCreateRequest`:
- `prompt_set_id` (non-empty)
- `input_image` (non-empty, a filename under `data/input_images/`)
- `model_ids` (≥1)
- `prompt_keys` (list; empty = all prompts in the set; keys are `baseline`, `equivalent`, and variation names)
- `execution_mode` — fixed to `provider` by the UI; `mock` is available via the API for testing

### 7.3 Run record

Each run is stored under `data/output_runs/<run_id>/` containing the generated images plus `manifest.json` and `index.json`. The detailed record (`RunIndex`) includes:

- `run_id`, `generated_at`, `prompt_set_id`, `input_image`, `execution_mode`
- `selected_models[]` — `{ id, display_name }`
- `prompts[]` — `{ key, label, prompt, prompt_kind, variation_type, similarity_to_baseline }`
- `items[]` — one per (model × prompt): `model_id`, `model_display_name`, `prompt_key`, `prompt_label`, `prompt_kind`, `variation_type`, `similarity_to_baseline`, `prompt_text`, `output_file`, `image_path`, `timestamp`, and timing fields (`generation_elapsed_s`, `provider_elapsed_s`, `download_elapsed_s`), plus optional `request_payload` / `raw_response`.

`run_id` format: a UTC timestamp + prompt-set id, e.g. `20260613T064718Z_identity_pixel_art`.

### 7.4 Asynchronous run jobs

In addition to the synchronous create endpoint, runs can be executed as background jobs with progress polling (`RunJobService`). A `RunJob` carries `job_id`, `status` (`queued` | `running` | `completed` | `failed`), timestamps, `completed_steps` / `total_steps`, the current model/prompt, a `message`, and (on success) the resulting `run_id`, or an `error`.

## 8. Input images

Read from `data/input_images/`. Supported: `.png`, `.jpg`, `.jpeg`, `.webp`. v1 supports exactly one input image per run. Listed via the runtime API; served as static files.

## 9. Model registry

Backend-owned (`core/model_registry.py`); a frontend-safe subset (`id`, `display_name`, `provider`, `description`) is exposed via the API. Secrets and low-level request templates stay backend-only. Currently registered models:

| id | provider | display name |
|---|---|---|
| `openai:gpt-image-2:edit` | openai | GPT Image 2 Edit |
| `fal:fal-ai/nano-banana-2/edit` | fal | Nano Banana 2 Edit |
| `fal:fal-ai/flux-2-pro/edit` | fal | FLUX.2 Pro Edit |
| `fal:fal-ai/flux-pro/kontext` | fal | FLUX.1 Kontext Pro |
| `fal:fal-ai/bytedance/seedream/v5/lite/edit` | fal | Seedream 5 Lite Edit |
| `fal:ideogram/v4/image-to-image` | fal | Ideogram V4 Image-to-Image |
| `fal:xai/grok-imagine-image/edit` | fal | Grok Imagine Image Edit |

## 10. Backend API

All routes are under `/api`.

### Runtime (`/api`)
- `GET /api/health` → `{ "status": "ok" }`
- `GET /api/models` → frontend-safe model metadata list
- `GET /api/input-images` → available input image `{ file_name, url }`

### Prompt sets (`/api/prompt-sets`)
- `GET /api/prompt-sets` → summaries (`prompt_set`, `baseline_prompt`, `variation_count`, `has_equivalent`)
- `GET /api/prompt-sets/{prompt_set_id}` → one full prompt set
- `POST /api/prompt-sets/generate` → generate prompts from a baseline (no persistence)
- `POST /api/prompt-sets` → create (validates uniqueness, recomputes similarity, writes) → 201
- `PUT /api/prompt-sets/{prompt_set_id}` → update in place
- `POST /api/prompt-sets/{prompt_set_id}/recompute-similarity` → recompute and save

### Runs (`/api/runs`)
- `GET /api/runs` → run summaries
- `GET /api/runs/{run_id}` → full run record (404 if missing)
- `POST /api/runs` → create a run synchronously → 201
- `POST /api/runs/jobs` → start a background run job → 202
- `GET /api/runs/jobs/{job_id}` → poll job status

### Static mounts
- `/static/input-images/<name>` → files from `data/input_images/`
- `/static/output-runs/<run_id>/<file>` → files from `data/output_runs/`

## 11. UI pages

1. **Prompt Sets** — browse existing sets; start a new one; select one to inspect/edit or proceed to a run.
2. **Prompt Builder** — baseline textarea, include-equivalent toggle, variation-count input, generate/regenerate, editable prompt cards, recompute similarity, save. All prompt cards share a uniform layout with equal-height textareas (see DESIGN.md).
3. **Run configuration** — selected prompt-set summary, input-image selector with thumbnail, multi-select model list, prompt-selection checkboxes, run button.
4. **Run results** — run metadata, per-model comparison grid (prompt text row above generated-image row), baseline first, then `equivalent`, then variations in saved order. Past runs are browsable from a sidebar.

## 12. Error handling

The backend returns structured HTTP errors for: missing environment variables (e.g. similarity/generation without `OPENAI_API_KEY` → 4xx), malformed prompt-set files (HTTP 422 with precise line/field info — see §6.1), invalid generation responses, provider failures, missing input image, and unknown model id / prompt key. The frontend surfaces actionable error text tied to the affected step.

## 13. Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `OPENAI_API_KEY` | prompt generation, similarity, OpenAI image model | — (required for those features) |
| `FAL_KEY` | FAL-hosted image models | — (required for FAL runs) |
| `PROMPT_LLM_MODEL` | prompt-rewrite model | `gpt-5.5` |
| `PROMPT_EMBEDDING_MODEL` | similarity embedding model | `text-embedding-3-large` |

Loaded via `python-dotenv` (`load_dotenv()` with no path — searches CWD upward) plus `os.getenv`. Keys may come from a repo-root `.env` **or** the machine environment. No keys are stored in frontend code or persisted into prompt-set/run files.

## 14. Persistence rules

- **Prompt sets:** saving reads the catalog, validates `prompt_set` uniqueness, recomputes `similarity_to_baseline`, and writes `data/prompt_sets/prompt_sets.json` atomically (temp file + replace).
- **Runs:** running creates `data/output_runs/<run_id>/` with image files, `manifest.json`, and `index.json`.

## 15. Open / future decisions

- Parallel run execution (currently sequential).
- Exposing per-model parameter editing in the UI.
- Import tooling for historical run metadata (legacy CLI outputs are archived under `legacy/`, not migrated).
