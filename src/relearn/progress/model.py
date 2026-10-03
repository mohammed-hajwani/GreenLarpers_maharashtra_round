import json
import random
from datetime import UTC, datetime
from functools import lru_cache

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from relearn.config import load_config
from relearn.progress.simulator import ASSUMPTIONS, trajectory

TARGETS = ("reach_mastery", "misconception_persists")
LABEL = "Estimate based on simulated learners, not validated on real students."
SIZES = {"train": 2400, "val": 600, "test": 1000}


def model_dir():
    return load_config().path("models_dir") / "progress"


def dataset(seed: int, n: int) -> tuple[list[str], np.ndarray, dict[str, np.ndarray]]:
    rng = random.Random(seed)
    rows = [trajectory(rng) for _ in range(n)]
    names = list(rows[0][0])
    x = np.array([[r[0][k] for k in names] for r in rows])
    y = {"reach_mastery": np.array([r[1] for r in rows]), "misconception_persists": np.array([r[2] for r in rows])}
    return names, x, y


def _scores(y: np.ndarray, p: np.ndarray) -> dict:
    return {
        "n": int(len(y)),
        "base_rate": float(y.mean()),
        "auc": float(roc_auc_score(y, p)),
        "brier": float(brier_score_loss(y, p)),
        "accuracy": float(accuracy_score(y, p >= 0.5)),
    }


def train(seed: int | None = None) -> dict:
    seed = load_config().seed if seed is None else seed
    splits = {}
    for i, (name, n) in enumerate(SIZES.items()):
        names, x, y = dataset(seed + 1000 * (i + 1), n)
        splits[name] = (x, y)
    chosen, report = {}, {}
    for target in TARGETS:
        candidates = {
            "logistic_regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000)),
            "hist_gradient_boosting": HistGradientBoostingClassifier(max_iter=200, random_state=seed),
        }
        val_auc = {}
        for cname, clf in candidates.items():
            clf.fit(splits["train"][0], splits["train"][1][target])
            val_auc[cname] = float(roc_auc_score(splits["val"][1][target], clf.predict_proba(splits["val"][0])[:, 1]))
        best = max(val_auc, key=val_auc.get)
        clf = candidates[best]
        test_p = clf.predict_proba(splits["test"][0])[:, 1]
        chosen[target] = clf
        report[target] = {"model": best, "val_auc": val_auc, "test": _scores(splits["test"][1][target], test_p)}
    meta = {
        "name": "progress_predictor",
        "version": "1",
        "training_date": datetime.now(UTC).isoformat(timespec="seconds"),
        "training_dataset": {
            "data_provenance": "simulated learner trajectories",
            "generator": "relearn.progress.simulator",
            "assumptions": ASSUMPTIONS,
            "split_sizes": SIZES,
            "seed": seed,
        },
        "feature_method": "history features over the first 10 practice steps",
        "features": names,
        "targets": list(TARGETS),
        "metrics": report,
        "label": LABEL,
    }
    directory = model_dir()
    directory.mkdir(parents=True, exist_ok=True)
    joblib.dump({"features": names, "models": chosen}, directory / "model.joblib", compress=3)
    (directory / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


@lru_cache(maxsize=1)
def load() -> dict | None:
    path = model_dir() / "model.joblib"
    return joblib.load(path) if path.exists() else None


def predict(feats: dict[str, float]) -> dict | None:
    bundle = load()
    if bundle is None:
        return None
    x = np.array([[feats[k] for k in bundle["features"]]])
    out = {target: float(clf.predict_proba(x)[0, 1]) for target, clf in bundle["models"].items()}
    return {**out, "label": LABEL}
