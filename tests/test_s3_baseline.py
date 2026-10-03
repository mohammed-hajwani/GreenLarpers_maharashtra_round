import numpy as np
import pytest

from relearn.config import load_config
from relearn.data.pipeline import build_splits
from relearn.models.baseline import texts_of, train_baseline
from relearn.models.calibration import fit_temperature_from_logits
from relearn.models.evaluation import evaluate_model
from relearn.models.registry import BASELINE, load_model


@pytest.fixture(scope="module")
def trained():
    cfg = load_config()
    splits = build_splits(cfg)
    return cfg, splits, train_baseline(splits["train"], cfg)


def test_baseline_macro_f1(trained) -> None:
    cfg, splits, model = trained
    result = evaluate_model(model, splits["test"])
    assert result["model_only"]["macro_f1"] >= cfg.baseline.min_macro_f1


def test_temperature_fit(trained) -> None:
    _, splits, model = trained
    val = splits["val"]
    targets = np.array([model.labels.index(s.misconception_label) for s in val])
    t = fit_temperature_from_logits(model.logits(texts_of(val)), targets)
    assert 0.1 <= t <= 5.0


def test_committed_baseline_loads() -> None:
    model = load_model(BASELINE)
    assert len(model.labels) == 13
    assert model.predict(["a puck slides [sep] 0 n || no force needed"])[0] in model.labels
