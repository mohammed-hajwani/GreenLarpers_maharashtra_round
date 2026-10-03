import pytest
from streamlit.testing.v1 import AppTest

from relearn.app.demo import run_demo
from relearn.config import ROOT
from relearn.learner.store import LearnerStore
from relearn.llm.stub import StubLLMClient
from relearn.models.loader import load_chain
from relearn.pipeline import Tutor

APP = str(ROOT / "app.py")


@pytest.fixture(autouse=True)
def no_keys(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("RELEARN_DB", str(tmp_path / "k.db"))


def test_full_flow_without_api_key_on_baseline_fallback(tmp_path) -> None:
    active = load_chain(("baseline",))
    tutor = Tutor(LearnerStore(tmp_path / "b.db"), active.model)
    assert isinstance(tutor.llm, StubLLMClient)
    steps = run_demo(tutor)
    assert [s["kind"] for s in steps][-1] == "profile"
    assert next(s for s in steps if s["kind"] == "retest")["data"]["state"] == "resolved"


def _start_demo(at: AppTest) -> None:
    at.run()
    at.sidebar.radio[0].set_value("Demo mode")
    at.run()
    next(b for b in at.button if b.label == "Start demo").click()
    at.run()
    next(b for b in at.button if b.label == "Show all").click()
    at.run()


def test_app_demo_live() -> None:
    at = AppTest.from_file(APP, default_timeout=180)
    _start_demo(at)
    assert not at.exception
    assert not any("REPLAY" in e.value for e in at.error)
    assert any("RESOLVED" in s.value for s in at.success)
    assert any("Active model" in m.value for m in at.markdown)


def test_app_demo_replay_is_labeled(monkeypatch) -> None:
    monkeypatch.setattr("relearn.services.get_active_model", lambda: load_chain(()))
    monkeypatch.setattr("relearn.app.streamlit_app.get_tutor", lambda: Tutor(LearnerStore(":memory:"), None))
    at = AppTest.from_file(APP, default_timeout=180)
    _start_demo(at)
    assert not at.exception
    assert any("REPLAY" in e.value for e in at.error)
    assert any("RESOLVED" in s.value for s in at.success)


def test_health_query() -> None:
    at = AppTest.from_file(APP, default_timeout=180)
    at.query_params["health"] = "1"
    at.run()
    assert at.markdown[0].value == "ok"
    assert at.markdown[1].value.startswith("model: ")
