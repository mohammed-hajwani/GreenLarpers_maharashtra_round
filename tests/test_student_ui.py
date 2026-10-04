import pytest
from streamlit.testing.v1 import AppTest
from test_ui_separation import BANNED, page_text

from relearn.config import ROOT
from relearn.learning.flow import LESSON_LENGTH
from relearn.learning.guided import STEPS

APP = str(ROOT / "app.py")


@pytest.fixture
def at(tmp_path, monkeypatch) -> AppTest:
    monkeypatch.setenv("RELEARN_DB", str(tmp_path / "ui.db"))
    app = AppTest.from_file(APP, default_timeout=180)
    app.query_params["view"] = "learn"
    app.run()
    return app


def clean(app: AppTest, where: str) -> None:
    assert not app.exception, where
    text = page_text(app).lower()
    hits = [b for b in BANNED if b.lower() in text]
    assert not hits, (where, hits)


def press(app: AppTest, key: str) -> None:
    app.button(key=key).click()
    app.run()


def test_guided_demo_screens_are_clean(at) -> None:
    clean(at, "landing")
    press(at, "start-demo")
    clean(at, "demo start")
    statuses = []
    locked = False
    for i in range(len(STEPS)):
        press(at, "demo-next")
        clean(at, f"demo step {i + 1}")
        assert at.session_state["rl_guided_last"], f"step {i + 1} shows no student input"
        if i == 0:
            banner = next(m.value for m in at.markdown if "What the student just did" in m.value)
            assert "2.7 N" in banner and "What the student just did" in banner
        locked = locked or any("Locked in for now" in m.value for m in at.markdown)
        flow = at.session_state["rl_flow"]
        statuses.append(flow.feedback.status if flow.feedback else flow.phase)
    assert {"quick_check", "incorrect", "revealed", "correct"} <= set(statuses)
    assert locked
    press(at, "demo-exit")
    assert at.session_state["rl_screen"] == "landing"


def _form_answer(app: AppTest, text: str, working: str) -> None:
    app.text_input[0].input(text)
    app.text_area[0].input(working)
    next(b for b in app.button if b.label == "Check answer").click()
    app.run()


def test_live_lesson_actions(at) -> None:
    press(at, "start-force_motion")
    clean(at, "lesson question")
    flow = at.session_state["rl_flow"]
    assert any("Question 1 of 5" in m.value for m in at.markdown)
    first = flow.item.question.question_id
    for _ in range(3):
        if flow.phase == "quick_check":
            probe = flow.pending["choice"].probe
            at.radio[0].set_value(probe.options[0])
            next(b for b in at.button if b.label == "Check answer").click()
            at.run()
        elif flow.phase == "question":
            if flow.item.question.question_type.value == "mcq":
                at.radio[0].set_value(next(o for o in flow.item.question.options if o != flow.item.answer_display))
                at.text_area[0].input("a force is needed to keep it moving forward")
                next(b for b in at.button if b.label == "Check answer").click()
                at.run()
            else:
                _form_answer(at, "100 N forward", "a force is needed to keep it moving forward")
        clean(at, f"after answer, phase {flow.phase}")
    assert flow.feedback.status == "incorrect"
    assert any("work through this" in m.value for m in at.markdown)
    press(at, "nav-reveal")
    clean(at, "revealed")
    assert flow.revealed and any("Why it works" in m.value for m in at.markdown)
    press(at, "nav-try_another")
    clean(at, "try another")
    assert flow.item.question.question_id != first and flow.phase == "question"
    assert at.session_state["rl_flow"].completed == 0


def test_completion_screen(at) -> None:
    press(at, "start-free_fall")
    flow = at.session_state["rl_flow"]
    flow.completed = LESSON_LENGTH
    flow.phase, flow.item, flow.feedback = "complete", None, None
    at.run()
    clean(at, "complete")
    assert any("Lesson complete" in m.value for m in at.markdown)
    press(at, "all-lessons")
    assert at.session_state["rl_screen"] == "landing"


def test_health_still_ok(at) -> None:
    app = AppTest.from_file(APP, default_timeout=180)
    app.query_params["health"] = "1"
    app.run()
    assert app.markdown[0].value == "ok"
