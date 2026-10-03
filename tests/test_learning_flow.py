import pytest

from relearn import services as svc
from relearn.content import load_content
from relearn.learner.store import LearnerStore
from relearn.learning.flow import LESSON_LENGTH, VISIT_CAP, LessonEngine
from relearn.learning.guided import STEPS, start_demo
from relearn.learning.items import practice_item, variant
from relearn.models.loader import get_active_model
from relearn.pipeline import Tutor

BANNED = [
    "decision trace",
    "why the ai",
    "sources used",
    "strategy",
    "model evaluation",
    "confidence",
    "probability",
    "misconception",
]
WRONG = ("2.7 N", "The force from the hit keeps it moving forward.")


@pytest.fixture
def engine(tmp_path) -> LessonEngine:
    return LessonEngine(Tutor(LearnerStore(tmp_path / "flow.db"), get_active_model().model))


def _template(tid: str):
    return next(t for t in load_content().templates if t.template_id == tid)


def _kicked(engine: LessonEngine):
    return engine.start("S", "force_motion", item=practice_item(_template("m09_kicked_ball_02"), {"m": 0.45, "v": 6}))


def _clear_quick_checks(engine, flow, held="M01"):
    while flow.phase == "quick_check":
        probe = flow.pending["choice"].probe
        engine.answer_quick_check(flow, probe.expected_answer_by_label.get(held, probe.options[0]))
    return flow.feedback


def _student_text(fb) -> str:
    return " ".join([fb.message, fb.hint, fb.answer, fb.explanation]).lower()


def test_correct_answer(engine) -> None:
    flow = engine.start("S", "force_motion", item=practice_item(_template("m01_puck_ice_01"), {"m": 0.5, "v": 8}))
    fb = engine.check(flow, "0 N", "No net force is needed at constant velocity.")
    fb = _clear_quick_checks(engine, flow)
    assert fb.status == "correct" and fb.explanation and fb.answer == "0 N"
    history = engine.tutor.store.mastery_history("S")
    assert history[-1]["after"] > history[-1]["before"]


def test_incorrect_hint_try_again_and_escalation(engine) -> None:
    flow = _kicked(engine)
    engine.check(flow, *WRONG)
    fb = _clear_quick_checks(engine, flow)
    assert fb.status == "incorrect" and fb.hint.startswith("Here's a hint")
    assert not any(b in _student_text(fb) for b in BANNED)
    assert "Key idea" not in fb.hint
    engine.try_again(flow)
    assert flow.phase == "question" and flow.feedback is None
    engine.check(flow, *WRONG)
    fb = _clear_quick_checks(engine, flow)
    assert "Key idea" in fb.hint
    assert not any(b in _student_text(fb) for b in BANNED)


def test_reveal_is_logged_and_not_mastery_evidence(engine) -> None:
    flow = _kicked(engine)
    engine.check(flow, *WRONG)
    _clear_quick_checks(engine, flow)
    before = len(engine.tutor.store.mastery_history("S"))
    fb = engine.reveal(flow)
    assert fb.status == "revealed" and fb.answer == "0 N" and fb.explanation
    assert len(engine.tutor.store.mastery_history("S")) == before
    reveal = [e for e in engine.tutor.store.timeline("S") if e["kind"] == "reveal"]
    assert reveal and reveal[0]["revealed"] is True
    engine.try_again(flow)
    assert flow.phase == "feedback"
    engine.continue_(flow)
    assert flow.completed == 1 and flow.phase == "question"


def test_try_another_same_concept_and_mix_up(engine) -> None:
    flow = _kicked(engine)
    engine.check(flow, *WRONG)
    _clear_quick_checks(engine, flow)
    first_id = flow.item.question.question_id
    mix_up = flow.mix_up
    engine.reveal(flow)
    engine.try_another(flow)
    item = flow.item
    content = load_content()
    assert item.question.question_id != first_id
    assert content.concept_of(item.mix_up) == "force_motion"
    template = next(t for t in content.templates if t.template_id == item.template_id)
    assert mix_up == template.primary or mix_up in template.wrong
    assert flow.phase == "question" and flow.feedback is None and not flow.revealed


def test_no_repeats_in_session(engine) -> None:
    flow = _kicked(engine)
    ids = [flow.item.question.question_id]
    for _ in range(20):
        engine.try_another(flow)
        ids.append(flow.item.question.question_id)
    assert len(ids) == len(set(ids))


def test_exhausted_bank_message() -> None:
    concept = "free_fall"
    seen: set[str] = set()
    while (item := variant(concept, "M02", seen, 1)) is not None:
        seen.add(item.question.question_id)
    assert variant(concept, "M02", seen, 2) is None
    assert len(seen) > 20


def test_exhausted_try_another(engine, monkeypatch) -> None:
    flow = _kicked(engine)
    monkeypatch.setattr("relearn.learning.flow.variant", lambda *a, **k: None)
    fb = engine.try_another(flow)
    assert fb.status == "exhausted" and "keep going" in fb.message


def test_loop_cap_defers_and_flags_review(engine) -> None:
    flow = _kicked(engine)
    for _ in range(VISIT_CAP):
        if flow.phase == "feedback" and flow.feedback.status == "incorrect":
            engine.try_again(flow)
        engine.check(flow, *WRONG)
        _clear_quick_checks(engine, flow)
    assert flow.phase == "deferred" and "come back to this later" in flow.feedback.message
    assert any(e["kind"] == "review_flag" for e in engine.tutor.store.timeline("S"))
    engine.continue_(flow)
    assert flow.phase == "complete"
    assert svc.concept_status(engine.tutor, "S", "force_motion") == "review"


def test_screened_answer_not_counted(engine) -> None:
    flow = _kicked(engine)
    fb = engine.check(flow, "idk", "")
    assert fb.status == "needs_more" and flow.checks == 0 and flow.phase == "question"


def test_lockin_trap_failure_not_resolved(engine) -> None:
    flow = _kicked(engine)
    engine.check(flow, *WRONG)
    _clear_quick_checks(engine, flow)
    engine.try_another(flow)
    engine.check(flow, flow.item.answer_display, flow.item.explanation)
    _clear_quick_checks(engine, flow)
    engine.continue_(flow)
    assert flow.item.kind == "lockin"
    answers = []
    while flow.item is not None and flow.item.kind == "lockin":
        item = flow.item.assessment_item
        wrong_trap = item.kind == "trap"
        engine.check(flow, next(iter(item.trap_answer_maps_to)) if wrong_trap else flow.item.answer_display)
        answers.append(flow.feedback.status)
        engine.continue_(flow)
    assert "incorrect_item" in answers
    state = svc.misconception_states(engine.tutor, "S")[flow.mix_up]
    assert state != "resolved"
    assert svc.concept_status(engine.tutor, "S", "force_motion") != "mastered"


def test_lesson_completes(engine) -> None:
    flow = engine.start("S", "free_fall")
    for _ in range(40):
        if flow.phase == "complete":
            break
        if flow.phase == "question":
            engine.check(flow, flow.item.answer_display, flow.item.explanation)
            _clear_quick_checks(engine, flow, held="none")
        engine.continue_(flow)
    assert flow.phase == "complete" and flow.completed >= LESSON_LENGTH


def test_guided_demo_runs(engine) -> None:
    flow = start_demo(engine)
    for step in STEPS:
        step.action(engine, flow)
    assert flow.item.kind == "practice" and flow.phase == "question"
    assert any(e["kind"] == "reveal" for e in engine.tutor.store.timeline("guided-demo"))
    assert svc.misconception_states(engine.tutor, "guided-demo")["M01"] == "intervened"


def test_try_again_keeps_previous_hint_until_next_item(engine) -> None:
    flow = _kicked(engine)
    engine.check(flow, *WRONG)
    fb = _clear_quick_checks(engine, flow)
    engine.try_again(flow)
    assert flow.feedback is None and flow.previous_feedback is fb
    assert flow.previous_feedback.hint and flow.previous_feedback.visual_for
    engine.check(flow, "0 N", "Nothing pushes it forward once it leaves the foot.")
    _clear_quick_checks(engine, flow)
    engine.continue_(flow)
    if flow.phase == "question":
        assert flow.previous_feedback is None
