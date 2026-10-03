import pytest
from conftest import insights_app
from streamlit.testing.v1 import AppTest

from relearn.config import ROOT
from relearn.content import load_content
from relearn.data.generator import make_question

APP = str(ROOT / "app.py")


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("RELEARN_DB", str(tmp_path / "app.db"))


def _click(at: AppTest, label: str) -> None:
    next(b for b in at.button if b.label == label).click()
    at.run()


def test_health() -> None:
    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params["health"] = "1"
    at.run()
    assert not at.exception
    assert at.markdown[0].value == "ok"


def test_practice_flow_trap_fail_escalates() -> None:
    t = next(t for t in load_content().templates if t.template_id == "m01_car_cruise_02")
    q = make_question(t, {"v": 80})
    at = insights_app("AI practice console")
    at.session_state["question"] = q
    at.session_state["phase"] = "answer"
    at.run()
    next(r for r in at.radio if r.label == "Your answer").set_value(q.options[0])
    at.text_area[-1].input("The engine force must be bigger than friction or the car would stop.")
    _click(at, "Submit")
    assert at.session_state["phase"] == "diagnosed"
    assert at.session_state["diagnosis"].top_labels[0][0] == "M01"
    _click(at, "Help me with this")
    first = at.session_state["intervention"].strategy
    _click(at, "Check my understanding")
    items = at.session_state["assess_items"]
    stems = {i.stem: i for i in items}
    for r in at.radio:
        if r.label in stems:
            item = stems[r.label]
            r.set_value(next(iter(item.trap_answer_maps_to)) if item.kind == "trap" else item.correct_answer)
    _click(at, "Submit answers")
    result = at.session_state["last_result"]
    assert result["trap_passed"] is False
    assert result["state"] != "resolved"
    _click(at, "Try another explanation")
    assert at.session_state["intervention"].strategy != first
    assert not at.exception


def test_demo_page_runs() -> None:
    at = insights_app("AI demo walkthrough")
    _click(at, "Start demo")
    _click(at, "Show all")
    assert not at.exception
    assert any("RESOLVED" in s.value for s in at.success)
