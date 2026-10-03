from relearn.assessment.evaluator import evaluate_assessment
from relearn.assessment.planner import plan_assessment
from relearn.learner.state import new_record, on_assessment, on_diagnosis, on_intervention, on_retest
from relearn.learner.store import LearnerStore
from relearn.schemas import MisconceptionState

S = MisconceptionState


def test_unseen_to_active_needs_confidence() -> None:
    r = new_record("L", "M01")
    assert on_diagnosis(r, 0.3).state == S.unseen
    assert on_diagnosis(r, 0.7).state == S.active


def test_active_to_intervened() -> None:
    r = on_intervention(on_diagnosis(new_record("L", "M01"), 0.9), "counterexample")
    assert r.state == S.intervened
    assert r.strategies_tried == ["counterexample"]


def test_resolved_to_relapsed_to_intervened() -> None:
    r = new_record("L", "M01").model_copy(update={"state": S.resolved})
    r = on_diagnosis(r, 0.9)
    assert r.state == S.relapsed
    assert on_intervention(r, "analogy").state == S.intervened


def test_intervened_rediagnosed_goes_active() -> None:
    r = on_intervention(on_diagnosis(new_record("L", "M01"), 0.9), "counterexample")
    assert on_diagnosis(r, 0.9).state == S.active


def test_resolved_trap_fail_relapses() -> None:
    r = new_record("L", "M01").model_copy(update={"state": S.resolved})
    items = plan_assessment("M01")
    trap = items[-1]
    result = evaluate_assessment([trap], {trap.item_id: next(iter(trap.trap_answer_maps_to))})
    assert on_assessment(r, result).state == S.relapsed
    assert on_retest(r, result).state == S.relapsed


def test_posterior_moves() -> None:
    r = new_record("L", "M01")
    up = on_diagnosis(r, 0.8)
    assert up.alpha > r.alpha
    items = plan_assessment("M01")
    down = on_assessment(up, evaluate_assessment(items, {i.item_id: i.correct_answer for i in items}))
    assert down.beta > up.beta


def test_store_roundtrip(tmp_path) -> None:
    store = LearnerStore(tmp_path / "t.db")
    r = on_diagnosis(new_record("L", "M01"), 0.9)
    store.put(r, 7)
    assert store.get("L", "M01") == r
    assert store.retest_due("L", "M01") == 7
    store.log("L", "practice", "q1", "M01", False)
    store.log("L", "transfer", "i_m01_t1", "M01", True)
    assert store.attempt_count("L") == 2
    assert store.seen_items("L") == {"i_m01_t1"}
    store.reset("L")
    assert store.records("L") == []
