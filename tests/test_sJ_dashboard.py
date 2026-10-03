import json

import pytest
from streamlit.testing.v1 import AppTest

from relearn.analytics import dashboard_data, evaluation_data
from relearn.app.demo import run_demo
from relearn.config import ROOT
from relearn.learner.store import LearnerStore
from relearn.models.loader import get_active_model
from relearn.pipeline import Tutor

APP = str(ROOT / "app.py")


def test_empty_state(tmp_path) -> None:
    data = dashboard_data(LearnerStore(tmp_path / "e.db"), "nobody")
    assert data["empty"]
    assert data["overall_mastery"] is None
    assert data["average_confidence"] is None
    assert data["concept_mastery"] == [] and data["probe_effectiveness"] == []


def test_dashboard_values_come_from_store(tmp_path) -> None:
    tutor = Tutor(LearnerStore(tmp_path / "d.db"), get_active_model().model)
    run_demo(tutor)
    learner = "demo-learner"
    data = dashboard_data(tutor.store, learner)
    assert not data["empty"]
    stored = tutor.store.all_mastery(learner)
    assert data["overall_mastery"] == pytest.approx(sum(m.mean for m in stored.values()) / len(stored))
    history = tutor.store.mastery_history(learner)
    assert [r["mastery"] for r in data["mastery_over_time"]] == pytest.approx([h["after"] for h in history])
    traces = [t for t in tutor.store.traces(learner) if t["kind"] == "practice"]
    assert data["average_confidence"] == pytest.approx(sum(t["final"]["confidence"] for t in traces) / len(traces))
    assert len(data["probe_effectiveness"]) == sum(len(t["probes"]) for t in traces)
    assert data["intervention_effectiveness"]
    assert data["misconception_distribution"]


def test_evaluation_missing_file(tmp_path) -> None:
    assert evaluation_data(tmp_path / "missing.json") == {"available": False}


def test_evaluation_reads_real_file() -> None:
    data = evaluation_data()
    on_disk = json.loads((ROOT / "reports" / "metrics.json").read_text(encoding="utf-8"))
    assert data["metrics"] == on_disk
    assert data["metadata"]["v1_embedding"]["name"] == on_disk["models"]["v1_embedding"]["name"]


@pytest.mark.parametrize("page", ["Dashboard", "Model Evaluation"])
def test_pages_render(page: str, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("RELEARN_DB", str(tmp_path / "p.db"))
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    at.sidebar.radio[0].set_value(page)
    at.run()
    assert not at.exception


def test_evaluation_page_empty_state(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("relearn.analytics.load_config", lambda: type("C", (), {"path": lambda self, n: tmp_path})())
    assert evaluation_data() == {"available": False}
