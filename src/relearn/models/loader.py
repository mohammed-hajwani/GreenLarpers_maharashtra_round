import os
from dataclasses import dataclass
from functools import lru_cache

from relearn.models.base import TextClassifier
from relearn.models.registry import BASELINE, EMBEDDING, load_model, read_metadata

FORCE_ENV = "RELEARN_FORCE_MODEL"


@dataclass
class ActiveModel:
    model: TextClassifier | None
    source: str
    error: str = ""
    metadata: dict | None = None


def _load_embedding() -> TextClassifier:
    model = load_model(EMBEDDING)
    model.predict_proba(["warm up [sep] 0 n || warm up"])
    return model


def load_chain(order: tuple[str, ...]) -> ActiveModel:
    errors = []
    loaders = {EMBEDDING: _load_embedding, BASELINE: lambda: load_model(BASELINE)}
    for kind in order:
        try:
            return ActiveModel(loaders[kind](), kind, "; ".join(errors), read_metadata(kind))
        except Exception as exc:
            errors.append(f"{kind}: {type(exc).__name__}: {exc}")
    return ActiveModel(None, "replay", "; ".join(errors))


@lru_cache(maxsize=1)
def get_active_model() -> ActiveModel:
    forced = os.environ.get(FORCE_ENV, "")
    if forced == "none":
        return ActiveModel(None, "replay", "forced by RELEARN_FORCE_MODEL")
    if forced == BASELINE:
        return load_chain((BASELINE,))
    return load_chain((EMBEDDING, BASELINE))
