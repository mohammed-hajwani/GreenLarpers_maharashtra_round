import json
from pathlib import Path

import joblib

from relearn.models.baseline import BaselineModel

BASELINE_FILE = "baseline.joblib"
LABEL_MAP_FILE = "label_map.json"
TEMPERATURE_FILE = "temperature.json"


def save_baseline(model: BaselineModel, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    joblib.dump(model.pipeline, directory / BASELINE_FILE, compress=3)
    (directory / LABEL_MAP_FILE).write_text(
        json.dumps({str(i): label for i, label in enumerate(model.labels)}, indent=2), encoding="utf-8"
    )
    (directory / TEMPERATURE_FILE).write_text(
        json.dumps({"baseline": model.temperature}, indent=2), encoding="utf-8"
    )


def load_baseline(directory: Path) -> BaselineModel:
    pipeline = joblib.load(directory / BASELINE_FILE)
    temperature = json.loads((directory / TEMPERATURE_FILE).read_text(encoding="utf-8"))["baseline"]
    return BaselineModel(pipeline, temperature)
