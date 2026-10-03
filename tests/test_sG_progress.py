import json
import random

from relearn.analytics import dashboard_data
from relearn.app.demo import run_demo
from relearn.config import ROOT
from relearn.learner.store import LearnerStore
from relearn.models.loader import get_active_model
from relearn.pipeline import Tutor
from relearn.progress.features import learner_features
from relearn.progress.model import LABEL, load, predict
from relearn.progress.simulator import features, sample_learner, simulate, trajectory


def test_simulator_is_seeded() -> None:
    assert trajectory(random.Random(1)) == trajectory(random.Random(1))


def test_feature_names_match_model() -> None:
    events = simulate(random.Random(3), sample_learner(random.Random(3)), 10)
    assert list(features(events)) == load()["features"]


def test_held_out_metrics_reported() -> None:
    meta = json.loads((ROOT / "models" / "progress" / "metadata.json").read_text(encoding="utf-8"))
    assert meta["label"] == LABEL
    for target in ("reach_mastery", "misconception_persists"):
        test = meta["metrics"][target]["test"]
        assert test["n"] == 1000 and 0.5 <= test["auc"] <= 1.0
    m = json.loads((ROOT / "reports" / "metrics.json").read_text(encoding="utf-8"))
    assert m["progress_model"]["label"] == LABEL


def test_predictions_from_real_history(tmp_path) -> None:
    tutor = Tutor(LearnerStore(tmp_path / "g.db"), get_active_model().model)
    run_demo(tutor)
    feats = learner_features(tutor.store, "demo-learner", "force_motion")
    assert feats is not None and feats["attempts"] >= 1
    p = predict(feats)
    assert 0 <= p["reach_mastery"] <= 1 and 0 <= p["misconception_persists"] <= 1
    data = dashboard_data(tutor.store, "demo-learner")
    assert data["progress_label"] == LABEL and data["progress_estimates"]
