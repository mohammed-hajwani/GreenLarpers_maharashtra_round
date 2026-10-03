import importlib

from relearn.config import load_config
from relearn.schemas import Diagnosis, MisconceptionState


def test_packages_import() -> None:
    for name in [
        "relearn.schemas",
        "relearn.config",
        "relearn.llm",
        "relearn.data",
        "relearn.models",
        "relearn.diagnosis",
        "relearn.intervention",
        "relearn.assessment",
        "relearn.learner",
        "relearn.loops",
        "relearn.app",
    ]:
        importlib.import_module(name)


def test_config_loads() -> None:
    cfg = load_config()
    assert cfg.seed == 42
    assert cfg.diagnosis.top_k == 3
    assert cfg.loops["disambiguation"]["max_probes"] == 2


def test_schema_roundtrip() -> None:
    d = Diagnosis(top_labels=[("M01", 0.6), ("M09", 0.3)], is_correct=False, ambiguous=False)
    assert Diagnosis.model_validate_json(d.model_dump_json()) == d
    assert MisconceptionState("resolved") is MisconceptionState.resolved
