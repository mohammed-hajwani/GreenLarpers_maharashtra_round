import json

import numpy as np
import pytest

from relearn.config import load_config
from relearn.data.handwritten import load_handwritten
from relearn.data.pipeline import build_splits, clean_text, dedup_key
from relearn.models.baseline import sample_text, texts_of
from relearn.models.loader import load_chain
from relearn.models.registry import BASELINE, EMBEDDING, load_model, read_metadata

META_FIELDS = {"name", "version", "training_dataset", "training_date", "metrics", "feature_method", "classes"}


@pytest.fixture(scope="module")
def splits():
    return build_splits(load_config())


def test_no_template_leakage(splits) -> None:
    templates = {k: {s.question.template_id for s in v} for k, v in splits.items()}
    assert not templates["train"] & templates["test"]
    assert not templates["val"] & templates["test"]
    assert not templates["train"] & templates["val"]


def test_no_text_leakage(splits) -> None:
    train = set(texts_of(splits["train"]))
    assert not train & set(texts_of(splits["test"]))
    assert not train & set(texts_of(splits["val"]))


def test_deduplicated(splits) -> None:
    keys = [dedup_key(s) for v in splits.values() for s in v]
    assert len(keys) == len(set(keys))


def test_clean_text() -> None:
    assert clean_text("  a   force \n is ") == "a force is"


def test_handwritten_set() -> None:
    items = load_handwritten()
    assert len(items) >= 60
    assert {s.misconception_label for s in items} == set(load_model(BASELINE).labels)
    templates = {t for v in build_splits(load_config()).values() for t in texts_of(v)}
    assert not templates & {sample_text(s.question, s.response) for s in items}


@pytest.mark.parametrize("kind", [BASELINE, EMBEDDING])
def test_metadata(kind: str) -> None:
    meta = read_metadata(kind)
    assert META_FIELDS <= set(meta)
    assert meta["training_dataset"]["data_provenance"] == "synthetic"
    assert len(meta["classes"]) == 13


def test_embedding_model_predicts() -> None:
    model = load_model(EMBEDDING)
    p = model.predict_proba(["a ball is thrown [sep] 0 n || the force from my hand stays in the ball"])
    assert p.shape == (1, 13)
    assert np.isclose(p.sum(), 1.0)
    examples = model.similar_examples("x [sep] 0 n || the force from my hand stays in the ball", "M09")
    assert examples and -1.0 <= examples[0][1] <= 1.0


def test_loader_fallback_chain(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise OSError("hub unreachable")

    monkeypatch.setattr("relearn.models.loader._load_embedding", boom)
    active = load_chain((EMBEDDING, BASELINE))
    assert active.source == BASELINE and "hub unreachable" in active.error
    monkeypatch.setattr("relearn.models.registry.joblib.load", boom)
    assert load_chain((EMBEDDING, BASELINE)).source == "replay"


def test_metrics_report() -> None:
    m = json.loads((load_config().path("reports_dir") / "metrics.json").read_text(encoding="utf-8"))
    assert m["data_provenance"] == "synthetic"
    assert {BASELINE, EMBEDDING} <= set(m["models"])
    for kind in (BASELINE, EMBEDDING):
        assert "classification_report" in m["models"][kind]["test"]
        assert m["models"][kind]["handwritten"]["model_only"]["n"] >= 60
