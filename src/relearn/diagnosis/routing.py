from functools import lru_cache

import yaml

from relearn.config import ROOT

ACCEPT = "accept"
PROBE = "probe"
UNCERTAIN = "uncertain"
THRESHOLDS_PATH = ROOT / "configs" / "thresholds.yaml"


@lru_cache(maxsize=1)
def _load() -> dict:
    with THRESHOLDS_PATH.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def thresholds_for(model_kind: str | None) -> dict[str, float]:
    data = _load()
    return {**data["defaults"], **data.get("models", {}).get(model_kind or "", {})}


def open_set_threshold() -> float | None:
    section = _load().get("open_set")
    return float(section["threshold"]) if section else None


def open_set_score() -> str:
    section = _load().get("open_set") or {}
    return section.get("score", "msp")


def route_for(confidence: float, thresholds: dict[str, float]) -> str:
    if confidence >= thresholds["accept"]:
        return ACCEPT
    if confidence >= thresholds["probe"]:
        return PROBE
    return UNCERTAIN
