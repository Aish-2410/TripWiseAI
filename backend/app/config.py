"""Runtime configuration (environment-driven; secrets come only from the environment / git-ignored .env)."""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Secrets (GEMINI_API_KEY ...) live in backend/.env, which is git-ignored; real environment variables win over the file.
try:
    from dotenv import load_dotenv
    for _env in (ROOT / "backend" / ".env", ROOT / ".env"):
        load_dotenv(_env, override=False)
except ImportError:  # python-dotenv is optional: without it, set the variables in the shell
    pass
DATA_DIR = Path(os.getenv("TRIPWISE_DATA_DIR", ROOT / "datasets" / "processed"))
APP_DATA = Path(__file__).resolve().parent / "data"
DB_PATH = Path(os.getenv("TRIPWISE_DB", ROOT / "backend" / "tripwise.db"))
CORS_ORIGINS = [o.strip() for o in os.getenv("TRIPWISE_CORS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]

DEFAULT_CONFIG = {
    # Documented purpose of each weight is returned by GET /api/config.
    "weights": {"interest": 0.30, "budget": 0.25, "climate": 0.15, "duration": 0.15, "convenience": 0.10, "style": 0.05},
    "weight_docs": {
        "interest": "How well the destination's attractions and tags cover the traveller's interests.",
        "budget": "How comfortably the estimated trip cost fits the stated total budget.",
        "climate": "Match between preferred climate / season and the destination's (sample) climate data.",
        "duration": "Whether the requested trip length falls inside the destination's recommended range.",
        "convenience": "How quickly the traveller can reach the destination using allowed transport modes.",
        "style": "Fit with travel pace, group type and accessibility needs.",
    },
    "missing_component_score": 0.25,   # destination data missing -> low score, flagged as unverified
    "pace": {
        "relaxed": {"limit_min": 330, "max_activities": 3},
        "balanced": {"limit_min": 450, "max_activities": 4},
        "packed": {"limit_min": 570, "max_activities": 5},
    },
    "limited_budget_per_person_day": 2500,
    "short_trip_days": 2,
    "beam_width": 40,
    "contingency_pct": 0.08,
    "local_km_rate": 14.0,
    "local_road_factor": 1.35,
}


def load_config() -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    p = APP_DATA / "config.json"
    if p.exists():
        try:
            user = json.loads(p.read_text(encoding="utf-8"))
            for k, v in user.items():
                if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                    cfg[k].update(v)
                else:
                    cfg[k] = v
        except (OSError, json.JSONDecodeError):
            pass
    return cfg
