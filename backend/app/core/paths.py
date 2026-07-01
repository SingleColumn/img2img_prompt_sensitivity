from __future__ import annotations

from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = APP_ROOT / "data"
PROMPT_SETS_DIR = DATA_DIR / "prompt_sets"
PROMPT_SETS_FILE = PROMPT_SETS_DIR / "prompt_sets.json"
INPUT_IMAGES_DIR = DATA_DIR / "input_images"
OUTPUT_RUNS_DIR = DATA_DIR / "output_runs"

