"""Optional Stravl-trained affinity signal (logistic regression, pure-numpy inference).

Only destinations that exist in BOTH the sample dataset and Stravl can be scored (5 of 16).
This is informational: it never changes the deterministic ranking.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np

from ..config import APP_DATA, DATA_DIR
from ..ml.stravl_pipeline import EXP, SCN, score_with_model

STRAVL_NAME = {"goa": "Panaji, India", "agra": "Agra, India", "jaipur": "Jaipur, India", "varanasi": "Varanasi, India", "mysuru": "Mysore, India"}
INTEREST_TO_EXP = {"beaches": "beach", "adventure": "adventure", "nature": "nature", "culture": "culture", "historical": "history", "shopping": "shopping", "food": "cuisine"}
INTEREST_TO_SCN = {"beaches": "sea", "mountains": "mountain", "nature": "jungle", "adventure": "mountain", "wellness": "rural",
                   "historical": "urban", "culture": "urban", "shopping": "urban", "food": "urban"}
PACE_TO_ACT = {"relaxed": 0.0, "balanced": 1.0, "packed": 2.0}


@lru_cache(maxsize=1)
def _model() -> dict | None:
    p = APP_DATA / "stravl_model.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


@lru_cache(maxsize=1)
def metrics() -> dict | None:
    p = Path(DATA_DIR) / "stravl_ml_metrics.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def affinity(dest_id: str, prefs) -> dict | None:
    m = _model()
    if m is None or dest_id not in STRAVL_NAME:
        return None
    idx = m["destination_index"].get(STRAVL_NAME[dest_id])
    if idx is None:
        return None
    exp = np.zeros(len(EXP), np.float32); scn = np.zeros(len(SCN), np.float32)
    for it in prefs.interests:
        if it in INTEREST_TO_EXP:
            exp[EXP.index(INTEREST_TO_EXP[it])] = 1.0
        if it in INTEREST_TO_SCN:
            scn[SCN.index(INTEREST_TO_SCN[it])] = 1.0
    if exp.sum() == 0 and scn.sum() == 0:
        return dict(available=False, reason="Add at least one interest that maps to a Stravl experience or scenery category.")
    p = score_with_model(m, exp, scn, PACE_TO_ACT[prefs.pace], 1.0, idx)
    base = float(1 / (1 + np.exp(-np.log(np.clip(m["profiles"]["rate"][idx], 1e-3, 1 - 1e-3) / (1 - np.clip(m["profiles"]["rate"][idx], 1e-3, 1 - 1e-3))))))
    return dict(available=True, stravl_destination=STRAVL_NAME[dest_id], p_yes=round(p, 3), destination_base_rate=round(base, 3),
                n_swipes=int(m["profiles"]["yes_n"][idx] + m["profiles"]["no_n"][idx]),
                note="Probability that a Stravl traveller with these preferences swiped 'yes' on this destination. Informational only.")
