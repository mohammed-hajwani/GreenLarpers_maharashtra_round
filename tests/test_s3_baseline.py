import numpy as np
import pytest

from relearn.config import load_config
from relearn.data.generator import generate_dataset
from relearn.data.splits import split_by_template
from relearn.models.artifacts import load_baseline, save_baseline
from relearn.models.baseline import texts_of, train_baseline
from relearn.models.calibration import fit_temperature_from_logits
from relearn.models.evaluation import evaluate_model


@pytest.fixture(scope="module")
def trained():
    cfg = load_config()
    splits = split_by_template(generate_dataset(cfg), cfg)
    return cfg, splits, train_baseline(splits["train"], cfg)


def test_baseline_macro_f1(trained) -> None:
    cfg, splits, model = trained
    result = evaluate_model(model, splits["test"])
    assert result["model_only"]["macro_f1"] >= cfg.baseline.min_macro_f1


def test_save_and_reload(trained, tmp_path) -> None:
    _, splits, model = trained
    val = splits["val"]
    targets = np.array([model.labels.index(s.misconception_label) for s in val])
    model.temperature = fit_temperature_from_logits(model.logits(texts_of(val)), targets)
    save_baseline(model, tmp_path)
    loaded = load_baseline(tmp_path)
    texts = texts_of(val[:20])
    assert np.allclose(loaded.predict_proba(texts), model.predict_proba(texts))


def test_committed_artifacts_load() -> None:
    cfg = load_config()
    model = load_baseline(cfg.path("artifacts_dir"))
    assert len(model.labels) == 13
