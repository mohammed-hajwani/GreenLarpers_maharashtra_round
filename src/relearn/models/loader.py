import os
from dataclasses import dataclass
from functools import lru_cache

from relearn.config import load_config
from relearn.models.artifacts import load_baseline
from relearn.models.baseline import BaselineModel


@dataclass
class ActiveModel:
    model: BaselineModel | None
    source: str
    error: str = ""


def _try_hub() -> BaselineModel | None:
    if not os.environ.get("HF_MODEL_REPO"):
        return None
    return None


@lru_cache(maxsize=1)
def get_active_model() -> ActiveModel:
    hub = _try_hub()
    if hub is not None:
        return ActiveModel(hub, "hub_transformer")
    try:
        return ActiveModel(load_baseline(load_config().path("artifacts_dir")), "baseline")
    except Exception as exc:
        return ActiveModel(None, "unavailable", str(exc))
