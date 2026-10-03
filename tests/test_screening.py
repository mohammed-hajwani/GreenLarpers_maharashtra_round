import pytest
from streamlit.testing.v1 import AppTest

from relearn.config import ROOT
from relearn.diagnosis.diagnoser import finalize
from relearn.diagnosis.screening import NEEDS_REASONING_MESSAGE, NON_ANSWER_MESSAGE, screen_response
from relearn.schemas import LearnerResponse, Question, QuestionType

CUSTOM = Question(
    question_id="custom",
    template_id="custom",
    question_type=QuestionType.explanation,
    stem="When do a feather and a block of iron reach the ground at the same time?",
    correct_answer="",
)
KEYED = CUSTOM.model_copy(update={"template_id": "t", "correct_answer": "In a vacuum"})


def _r(answer: str, working: str = "") -> LearnerResponse:
    return LearnerResponse(question_id="q", answer=answer, working=working)


@pytest.mark.parametrize("answer", ["idk", "IDK", "I don't know", "not sure", "?", "no idea!", "  "])
def test_non_answers_are_screened(answer: str) -> None:
    assert screen_response(KEYED, _r(answer)) == NON_ANSWER_MESSAGE


def test_custom_question_needs_reasoning() -> None:
    assert screen_response(CUSTOM, _r("same time")) == NEEDS_REASONING_MESSAGE
    assert screen_response(CUSTOM, _r("same time", "no air resistance so same acceleration")) is None
    assert screen_response(KEYED, _r("same time")) is None


def test_low_confidence_none_is_not_correct() -> None:
    d = finalize({"none": 0.41, "M02": 0.30, "M06": 0.29})
    assert not d.is_correct and d.route == "uncertain"
    assert d.misconception == "M02" and d.misconception_confidence == pytest.approx(0.30)
    sure = finalize({"none": 0.9, "M02": 0.1})
    assert sure.is_correct and sure.misconception is None


def test_app_screens_idk_on_custom_question(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("RELEARN_DB", str(tmp_path / "s.db"))
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    at.run()
    at.session_state["question"] = CUSTOM
    at.session_state["phase"] = "answer"
    at.run()
    at.text_input[0].input("idk")
    next(b for b in at.button if b.label == "Submit").click()
    at.run()
    assert at.session_state["phase"] == "answer"
    assert any("anything to diagnose" in w.value for w in at.warning)
    assert not any("Correct" in s.value for s in at.success)
