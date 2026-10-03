import json
from pathlib import Path

import joblib

from relearn.config import load_config
from relearn.models.base import TextClassifier
from relearn.models.baseline import BaselineModel
from relearn.models.embedding import EmbeddingModel

BASELINE = "baseline"
EMBEDDING = "v1_embedding"
MODEL_FILE = "model.joblib"
META_FILE = "metadata.json"


def model_dir(kind: str) -> Path:
    return load_config().path("models_dir") / kind


def read_metadata(kind: str) -> dict:
    path = model_dir(kind) / META_FILE
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_metadata(kind: str, metadata: dict) -> None:
    path = model_dir(kind) / META_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def update_metadata(kind: str, **fields) -> None:
    write_metadata(kind, {**read_metadata(kind), **fields})


def save_model(kind: str, model: TextClassifier, metadata: dict) -> None:
    directory = model_dir(kind)
    directory.mkdir(parents=True, exist_ok=True)
    if isinstance(model, BaselineModel):
        payload = {"pipeline": model.pipeline}
    else:
        payload = {
            "clf": model.clf,
            "encoder_name": model.encoder_name,
            "exemplars": model.exemplars,
            "tfidf": model.tfidf,
        }
    payload.update({"temperature": model.temperature, "version": model.version})
    joblib.dump(payload, directory / MODEL_FILE, compress=3)
    write_metadata(kind, metadata)


def load_model(kind: str) -> TextClassifier:
    payload = joblib.load(model_dir(kind) / MODEL_FILE)
    if kind == BASELINE:
        return BaselineModel(payload["pipeline"], payload["temperature"], payload["version"])
    return EmbeddingModel(
        payload["clf"],
        payload["encoder_name"],
        payload["temperature"],
        payload["version"],
        payload["exemplars"],
        payload.get("tfidf"),
    )
