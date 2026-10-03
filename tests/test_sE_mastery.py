import pytest

from relearn.assessment.evaluator import evaluate_assessment
from relearn.assessment.planner import plan_assessment
from relearn.content import load_content
from relearn.data.generator import make_question
from relearn.diagnosis.diagnoser import finalize
from relearn.learner.mastery import item_evidence, practice_evidence, prior, probe_evidence, update
from relearn.learner.state import new_record, on_assessment, on_intervention
from relearn.learner.store import LearnerStore
from relearn.pipeline import Tutor
from relearn.schemas import LearnerResponse, MisconceptionState


def _apply(evidence):
    _, record = update(prior(), "force_motion", "e", "r", evidence)
    return record


def test_correct_raises_mastery() -> None:
    r = _apply(practice_evidence(True, "medium", None))
    assert r.after > r.before


def test_harder_correct_raises_more() -> None:
    easy = _apply(practice_evidence(True, "easy", None))
    hard = _apply(practice_evidence(True, "hard", None))
    assert hard.after > easy.after


def test_misconception_lowers_mastery_by_confidence() -> None:
    weak = _apply(practice_evidence(False, "medium", finalize({"M01": 0.55, "M09": 0.45})))
    strong = _apply(practice_evidence(False, "medium", finalize({"M01": 0.95, "M09": 0.05})))
    assert weak.after < weak.before
    assert strong.after < weak.after
    assert strong.detail["misconception"] == "M01"


def test_probe_and_items() -> None:
    assert _apply(probe_evidence(True, False)).after < 0.5
    assert _apply(probe_evidence(False, True)).after > 0.5
    assert _apply(probe_evidence(False, False)).after == pytest.approx(0.5)
    assert _apply(item_evidence("trap", False)).after < _apply(item_evidence("transfer", False)).after


def test_high_mastery_never_resolves_after_trap_failure() -> None:
    items = plan_assessment("M01")
    answers = {i.item_id: i.correct_answer for i in items}
    trap = items[-1]
    answers[trap.item_id] = next(iter(trap.trap_answer_maps_to))
    record = on_assessment(
        on_intervention(new_record("L", "M01"), "counterexample"), evaluate_assessment(items, answers)
    )
    assert record.state != MisconceptionState.resolved


def test_pipeline_logs_before_after(tmp_path) -> None:
    tutor = Tutor(LearnerStore(tmp_path / "m.db"))
    t = next(t for t in load_content().templates if t.template_id == "m01_puck_ice_01")
    q = make_question(t, {"m": 0.5, "v": 8})
    d = tutor.submit(
        "L", q, LearnerResponse(question_id=q.question_id, answer="4.0 N forward", working="needs a force")
    )
    _, wrong = tutor.confirm("L", d, q)
    assert wrong.concept == "force_motion" and wrong.after < wrong.before
    d2 = tutor.submit("L", q, LearnerResponse(question_id=q.question_id, answer=q.correct_answer))
    _, right = tutor.confirm("L", d2, q)
    assert right.after > right.before
    history = tutor.store.mastery_history("L")
    assert [h["event"] for h in history] == ["practice", "practice"]
    assert history[0]["after"] == pytest.approx(history[1]["before"])
    assert tutor.store.mastery("L", "force_motion").mean == pytest.approx(history[-1]["after"])
    items = tutor.plan("L", "M01")
    answers = {i.item_id: i.correct_answer for i in items}
    answers[items[-1].item_id] = next(iter(items[-1].trap_answer_maps_to))
    result, record = tutor.submit_assessment("L", "M01", items, answers)
    assert record.state != MisconceptionState.resolved
    assert tutor.store.mastery_history("L")[-1]["event"] == "trap"
