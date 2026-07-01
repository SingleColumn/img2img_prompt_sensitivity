# img2img lab

A local web app for **image-to-image prompt sensitivity experiments**. You author a baseline image-edit prompt, generate semantically-equivalent rephrasings and variations of it, then run the whole set through one or more image-edit models and compare the outputs side by side. The goal is to *see* how much a model's output changes when the wording of a prompt changes but the intent does not.

This is a local-only demo: two processes on your machine (a Python backend and a React frontend), local files for storage, and provider API keys read from your environment. There is no cloud, no auth, no database.

---

## What it does

1. **Pick or create a prompt set** — a baseline prompt plus an `equivalent` rephrasing and any number of `variant_*` rewrites.
2. **Generate prompts** — an LLM rewrites your baseline into an equivalent and N variations, preserving the requested edit while changing the wording.
3. **Score similarity** — the backend embeds every prompt and computes cosine similarity to the baseline, so you can see how far each rewrite drifts semantically.
4. **Run an experiment** — choose one input image and one or more image-edit models; the backend edits the image once per (model × prompt).
5. **Compare results** — outputs are laid out in a grid so you can compare prompts within a model and across models.

---

## Prerequisites

- **Python 3.12+** (developed against 3.13)
- **Node.js 18+** (for Vite 5)
- API keys:
  - `OPENAI_API_KEY` — required for prompt generation, similarity scoring, and the OpenAI image model
  - `FAL_KEY` — required for the FAL-hosted image models

Keys are read from your environment via `python-dotenv` + `os.getenv`. You can either export them in your shell / system environment, or create a `.env` file at the repo root (copy `.env.example`). Keys are never written into prompt-set files or sent to the frontend.

---

## Running the app

The app is two processes. Start each in its own terminal. Commands below use **PowerShell** and assume you start from the repository root (`...\img2img_app` — note there is no `img2img_lab` subfolder).

### 1. Backend (port 8000)

```powershell
cd backend

# one-time setup
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# run — uses the venv's Python directly, no activation needed
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Backend serves at `http://127.0.0.1:8000`. Quick check: `http://127.0.0.1:8000/api/health` returns `{"status":"ok"}`.

> **Run from `backend/`, and use the venv's Python.** `app.main:app` is resolved relative to the current directory, so you must be inside `backend/`. The explicit `.\.venv\Scripts\python.exe -m uvicorn ...` form guarantees the venv interpreter is used. If instead you `python -m venv` then run a bare `uvicorn`, PowerShell will fall back to a *global* uvicorn and fail with `ModuleNotFoundError: No module named 'app'`.
>
> Prefer an activated prompt? In PowerShell that's `.\.venv\Scripts\Activate.ps1` (not `.venv\Scripts\activate`, which is cmd-only and silently does nothing here). If it's blocked by execution policy, run `Set-ExecutionPolicy -Scope Process RemoteSigned` first, then `uvicorn app.main:app --reload`.

### 2. Frontend (port 5173)

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

> **Port matters.** The frontend calls the backend at `http://127.0.0.1:8000`, and the backend's CORS policy only allows the frontend on **port 5173**. The dev server is pinned to 5173 with `strictPort: true`, so if 5173 is already in use Vite will **fail immediately with a clear error** rather than silently drifting to another port (which would break every API call with a CORS error). If that happens, free port 5173 — usually it's a leftover `npm run dev` from a previous session. If you ever need a different port, update both `frontend/vite.config.ts` and the `allow_origins` list in `backend/app/main.py` together.

---

## Configuration

Environment variables (all optional except where you need real provider calls):

| Variable | Required for | Default |
|---|---|---|
| `OPENAI_API_KEY` | prompt generation, similarity, OpenAI image model | — |
| `FAL_KEY` | FAL-hosted image models | — |
| `PROMPT_LLM_MODEL` | overrides the prompt-rewrite model | `gpt-5.5` |
| `PROMPT_EMBEDDING_MODEL` | overrides the similarity embedding model | `text-embedding-3-large` |

Prompt **generation** and **saving** a prompt set both call OpenAI (generation for the rewrite, saving to recompute similarity embeddings). Image runs call OpenAI or FAL depending on the selected model.

---

## Project layout

```
backend/          FastAPI backend
  app/
    api/          route handlers (prompt-sets, runs, runtime)
    core/         paths, config, model registry
    services/     catalog, similarity, run, run-job services
    schemas/      Pydantic models
    main.py       app + CORS + static mounts
  tests/
  requirements.txt
frontend/         React + TypeScript + Vite
  src/
    api/          backend client (API base = http://127.0.0.1:8000/api)
    styles/       design tokens + app CSS
    App.tsx
data/             local persistence (the app reads/writes only here)
  prompt_sets/prompt_sets.json   canonical prompt-set catalog
  input_images/                  source images (.png/.jpg/.jpeg/.webp)
  output_runs/<run_id>/          generated outputs + manifest.json + index.json
docs/
  SPEC.md         full functional + technical specification (as built)
  DESIGN.md       design system: tokens, component patterns, CSS rules
legacy/           pre-cutover CLI/viewer material — transitional, safe to delete
```

See [docs/SPEC.md](docs/SPEC.md) for the complete specification and [docs/DESIGN.md](docs/DESIGN.md) for the design system.
