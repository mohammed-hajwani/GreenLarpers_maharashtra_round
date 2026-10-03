import numpy as np
import yaml

from relearn.config import load_config
from relearn.data.pipeline import build_splits
from relearn.diagnosis.routing import THRESHOLDS_PATH
from relearn.models.baseline import texts_of
from relearn.models.evaluation import keyed
from relearn.models.registry import BASELINE, EMBEDDING, load_model

GRID = [0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95]
TARGET_PRECISION = 0.95
DEFAULTS = {"accept": 0.8, "probe": 0.5}


def tune(kind: str, val) -> dict:
    model = load_model(kind)
    probs = keyed(model.predict_proba(texts_of(val)), model.labels, val)
    conf = probs.max(axis=1)
    correct = np.array([model.labels[i] for i in probs.argmax(axis=1)]) == np.array(
        [s.misconception_label for s in val]
    )
    table = []
    accept = DEFAULTS["accept"]
    for t in GRID:
        mask = conf >= t
        precision = float(correct[mask].mean()) if mask.any() else 0.0
        table.append({"threshold": t, "coverage": float(mask.mean()), "precision": precision})
    passing = [row["threshold"] for row in table if row["precision"] >= TARGET_PRECISION]
    if passing:
        accept = min(passing)
    return {"accept": accept, "probe": DEFAULTS["probe"], "val_table": table}


def main() -> None:
    val = build_splits(load_config())["val"]
    out = {
        "defaults": DEFAULTS,
        "tuning": {"split": "val", "target_accept_precision": TARGET_PRECISION, "grid": GRID},
        "models": {kind: tune(kind, val) for kind in (EMBEDDING, BASELINE)},
    }
    THRESHOLDS_PATH.write_text(yaml.safe_dump(out, sort_keys=False), encoding="utf-8")
    for kind, row in out["models"].items():
        print(kind, row["accept"], row["probe"])


if __name__ == "__main__":
    main()
