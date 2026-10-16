"""Stravl travel-preference pipeline + optional ML ranker.

Task definition
---------------
Target  : for one (user, destination) swipe, did the user answer "yes" (1) or "no" (0)?
          ("maybe" swipes are dropped - ambiguous label.)
Inputs  : the user's stated trip preferences (experiences, scenery, activity level,
          safety attitude, popularity taste) and the destination's *profile*.
Profile : built ONLY from the training users' "yes" swipes (mean experience/scenery/
          activity/popularity of the people who liked it) -> no label leakage into
          the held-out users used for evaluation.
Split   : by USER (80/20), so no user appears in both train and test.
Models  : (a) popularity baseline, (b) content-similarity heuristic baseline,
          (c) logistic regression (deployed, interpretable, stored as JSON coefficients),
          (d) histogram gradient boosting (comparison only).
Metrics : ROC-AUC and average precision on held-out users.

Limitations are written to the metrics JSON and docs/DATASETS.md. The dataset is a
global, Western-skewed sample with only 13 Indian cities; the model is an OPTIONAL
signal and never replaces the deterministic recommender.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

EXP = ["beach", "adventure", "nature", "culture", "nightlife", "history", "shopping", "cuisine"]
SCN = ["urban", "rural", "sea", "mountain", "lake", "desert", "plains", "jungle"]
N_EXP, N_SCN = len(EXP), len(SCN)

FEATURE_NAMES = (
    [f"exp_match_{e}" for e in EXP]
    + [f"scn_match_{s}" for s in SCN]
    + ["neg_activity_gap", "neg_popularity_gap", "logit_dest_yes_rate", "cosine_profile", "n_matches"]
)


# ----------------------------------------------------------------- parsing
def parse_list(v: Any) -> list[int]:
    """Parse "['0', '2']" / "[837, 779]" style cells into ints. Bad cells -> []."""
    if isinstance(v, (list, tuple)):
        return [int(x) for x in v]
    if not isinstance(v, str) or not v.startswith("["):
        return []
    try:
        return [int(x) for x in ast.literal_eval(v)]
    except (ValueError, SyntaxError):
        return []


def _multi_hot(lst: list[int], n: int) -> np.ndarray:
    out = np.zeros(n, dtype=np.float32)
    for i in lst:
        if 0 <= i < n:
            out[i] = 1.0
    return out


def _single(v: Any, default: float = 1.0) -> float:
    lst = parse_list(v)
    return float(lst[0]) if lst else default


def load_users(csv_path: Path) -> pd.DataFrame:
    """Load the raw CSV and add parsed feature arrays. Rows with no experiences AND no scenery are dropped."""
    df = pd.read_csv(csv_path, usecols=["id", "form_f", "form_g", "form_h", "form_i", "form_j", "yes_swipes", "no_swipes"])
    return prepare_users(df)


def prepare_users(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["exp"] = df["form_f"].map(lambda v: _multi_hot(parse_list(v), N_EXP))
    df["scn"] = df["form_g"].map(lambda v: _multi_hot(parse_list(v), N_SCN))
    df["act"] = df["form_h"].map(_single)
    df["pop"] = df["form_j"].map(_single)
    df["yes"] = df["yes_swipes"].map(parse_list)
    df["no"] = df["no_swipes"].map(parse_list)
    keep = df["exp"].map(lambda a: a.sum() > 0) | df["scn"].map(lambda a: a.sum() > 0)
    return df[keep].reset_index(drop=True)


# ----------------------------------------------------------------- profiles
def build_profiles(train: pd.DataFrame, n_dest: int, prior_strength: float = 20.0) -> dict[str, np.ndarray]:
    """Per-destination profile computed from TRAIN users only."""
    exp_sum = np.zeros((n_dest, N_EXP)); scn_sum = np.zeros((n_dest, N_SCN))
    act_sum = np.zeros(n_dest); pop_sum = np.zeros(n_dest)
    yes_n = np.zeros(n_dest); no_n = np.zeros(n_dest)
    for e, s, a, p, y, n in zip(train["exp"], train["scn"], train["act"], train["pop"], train["yes"], train["no"]):
        for d in y:
            if 0 <= d < n_dest:
                exp_sum[d] += e; scn_sum[d] += s; act_sum[d] += a; pop_sum[d] += p; yes_n[d] += 1
        for d in n:
            if 0 <= d < n_dest:
                no_n[d] += 1
    g_exp = train["exp"].mean() if len(train) else np.full(N_EXP, 0.5)
    g_scn = train["scn"].mean() if len(train) else np.full(N_SCN, 0.5)
    g_act = float(train["act"].mean()) if len(train) else 1.0
    g_pop = float(train["pop"].mean()) if len(train) else 1.0
    total_yes, total_no = yes_n.sum(), no_n.sum()
    g_rate = total_yes / max(total_yes + total_no, 1.0)

    w = yes_n[:, None] / (yes_n[:, None] + prior_strength)  # shrink small-sample profiles to the global mean
    exp_p = w * (exp_sum / np.maximum(yes_n[:, None], 1)) + (1 - w) * np.asarray(g_exp)
    scn_p = w * (scn_sum / np.maximum(yes_n[:, None], 1)) + (1 - w) * np.asarray(g_scn)
    wa = yes_n / (yes_n + prior_strength)
    act_p = wa * (act_sum / np.maximum(yes_n, 1)) + (1 - wa) * g_act
    pop_p = wa * (pop_sum / np.maximum(yes_n, 1)) + (1 - wa) * g_pop
    rate = (yes_n + prior_strength * g_rate) / (yes_n + no_n + prior_strength)  # smoothed yes-rate
    return dict(exp=exp_p, scn=scn_p, act=act_p, pop=pop_p, rate=rate, yes_n=yes_n, no_n=no_n)


# ----------------------------------------------------------------- features
def _cos(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return float(a @ b / (na * nb)) if na > 0 and nb > 0 else 0.0


def pair_features(exp: np.ndarray, scn: np.ndarray, act: float, pop: float, prof: dict[str, np.ndarray], d: int) -> np.ndarray:
    de, ds = prof["exp"][d], prof["scn"][d]
    rate = float(np.clip(prof["rate"][d], 1e-3, 1 - 1e-3))
    em, sm = exp * de, scn * ds
    cos = _cos(np.concatenate([exp, scn]), np.concatenate([de, ds]))
    return np.concatenate([
        em, sm,
        [-abs(act - prof["act"][d]) / 2.0, -abs(pop - prof["pop"][d]) / 2.0, float(np.log(rate / (1 - rate))), cos,
         float((em > 0.5).sum() + (sm > 0.5).sum())],
    ]).astype(np.float32)


def build_pairs(users: pd.DataFrame, prof: dict[str, np.ndarray], max_pairs: int, rng: np.random.Generator):
    rows = []
    for ui, (yes, no) in enumerate(zip(users["yes"], users["no"])):
        for d in yes:
            rows.append((ui, d, 1))
        for d in no:
            rows.append((ui, d, 0))
    if not rows:
        return np.zeros((0, len(FEATURE_NAMES)), np.float32), np.zeros(0, int), np.zeros(0, int)
    rows = np.array(rows)
    if len(rows) > max_pairs:
        rows = rows[rng.choice(len(rows), max_pairs, replace=False)]
    n_dest = len(prof["rate"])
    exps, scns, acts, pops = users["exp"].to_numpy(), users["scn"].to_numpy(), users["act"].to_numpy(), users["pop"].to_numpy()
    X, y, keep = [], [], []
    for ui, d, lab in rows:
        if d >= n_dest:
            continue
        X.append(pair_features(exps[ui], scns[ui], acts[ui], pops[ui], prof, d))
        y.append(lab); keep.append(d)
    return np.vstack(X), np.array(y), np.array(keep)


# ----------------------------------------------------------------- training
def train_and_evaluate(users: pd.DataFrame, n_dest: int, test_size: float = 0.2, seed: int = 42,
                       max_train_pairs: int = 250_000, max_test_pairs: int = 80_000) -> tuple[dict, dict]:
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import average_precision_score, roc_auc_score
    from sklearn.preprocessing import StandardScaler

    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(users))
    n_test = int(len(users) * test_size)
    test_u, train_u = users.iloc[idx[:n_test]], users.iloc[idx[n_test:]]

    prof = build_profiles(train_u, n_dest)  # train users only -> no leakage
    Xtr, ytr, _ = build_pairs(train_u, prof, max_train_pairs, rng)
    Xte, yte, dte = build_pairs(test_u, prof, max_test_pairs, rng)

    def metrics(score):
        return dict(roc_auc=round(float(roc_auc_score(yte, score)), 4), avg_precision=round(float(average_precision_score(yte, score)), 4))

    pop_idx, cos_idx = FEATURE_NAMES.index("logit_dest_yes_rate"), FEATURE_NAMES.index("cosine_profile")
    scaler = StandardScaler().fit(Xtr)
    lr = LogisticRegression(max_iter=500, C=1.0).fit(scaler.transform(Xtr), ytr)
    hgb = HistGradientBoostingClassifier(max_iter=150, learning_rate=0.1, random_state=seed).fit(Xtr, ytr)

    report = dict(
        task="predict yes(1) vs no(0) swipe for a (user, destination) pair; 'maybe' swipes dropped",
        split="by user, 80/20, seed=%d" % seed,
        n_users_train=int(len(train_u)), n_users_test=int(len(test_u)), n_train_pairs=int(len(ytr)), n_test_pairs=int(len(yte)),
        positive_rate_test=round(float(yte.mean()), 4),
        models={
            "baseline_popularity (destination yes-rate)": metrics(Xte[:, pop_idx]),
            "baseline_content_similarity (cosine)": metrics(Xte[:, cos_idx]),
            "logistic_regression (deployed)": metrics(lr.predict_proba(scaler.transform(Xte))[:, 1]),
            "hist_gradient_boosting (comparison)": metrics(hgb.predict_proba(Xte)[:, 1]),
        },
        coefficients={n: round(float(c), 4) for n, c in zip(FEATURE_NAMES, lr.coef_[0])},
        limitations=[
            "Stravl is a global, self-selected web sample; swipes reflect photo-and-name impressions, not trip outcomes.",
            "Only 13 Indian cities are covered (no hill stations).",
            "Destination profiles are averages of who said yes; they encode popularity as much as fit.",
            "Budget in the form is USD per person per night and is not used.",
            "Optional signal only; the deterministic rule-based recommender remains the primary system.",
        ],
    )
    model = dict(
        feature_names=FEATURE_NAMES,
        scaler_mean=scaler.mean_.tolist(), scaler_scale=scaler.scale_.tolist(),
        coef=lr.coef_[0].tolist(), intercept=float(lr.intercept_[0]),
    )
    # profiles for every destination (full train set) so the runtime can score destinations
    full_prof = build_profiles(users, n_dest)
    model["profiles"] = {k: v.tolist() for k, v in full_prof.items() if k in ("exp", "scn", "act", "pop", "rate", "yes_n", "no_n")}
    return report, model


def score_with_model(model: dict, exp: np.ndarray, scn: np.ndarray, act: float, pop: float, dest_index: int) -> float:
    """P(yes) from the stored logistic-regression coefficients (pure numpy, no pickle)."""
    prof = {k: np.asarray(model["profiles"][k]) for k in ("exp", "scn", "act", "pop", "rate")}
    x = pair_features(exp, scn, act, pop, prof, dest_index)
    z = (x - np.asarray(model["scaler_mean"])) / np.maximum(np.asarray(model["scaler_scale"]), 1e-9)
    logit = float(z @ np.asarray(model["coef"]) + model["intercept"])
    return float(1.0 / (1.0 + np.exp(-logit)))


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    raw, out = root / "datasets" / "raw", root / "datasets" / "processed"
    names = [l.rstrip("\n") for l in (raw / "destination_ids.txt").read_text(encoding="utf-8").splitlines()]
    users = load_users(raw / "Stravl_Travel_Preference_Data.csv")
    report, model = train_and_evaluate(users, len(names))
    report["n_users_after_cleaning"] = int(len(users))
    india = {n: i for i, n in enumerate(names) if n.endswith(", India")}
    model["destination_index"] = {n: i for i, n in enumerate(names)}
    model["india"] = india
    (out / "stravl_ml_metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (root / "backend" / "app" / "data" / "stravl_model.json").write_text(json.dumps(model), encoding="utf-8")
    print(json.dumps(report["models"], indent=2)); print({k: report[k] for k in ("n_users_train", "n_users_test", "n_train_pairs", "n_test_pairs", "positive_rate_test")})


if __name__ == "__main__":
    main()
