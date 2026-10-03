from relearn.assessment.evaluator import evaluate_assessment, passes_reassessment, trap_misconceptions
from relearn.assessment.planner import plan_assessment, plan_retest
from relearn.learner.state import new_record, on_assessment, on_intervention, on_retest
from relearn.schemas import AssessmentItem, MisconceptionState


def _answers(items: list[AssessmentItem], correct_ids: set[str]) -> dict[str, str]:
    out = {}
    for i in items:
        if i.item_id in correct_ids:
            out[i.item_id] = i.correct_answer
        elif i.trap_answer_maps_to:
            out[i.item_id] = next(iter(i.trap_answer_maps_to))
        else:
            out[i.item_id] = next(o for o in i.options if o != i.correct_answer)
    return out


def _intervened():
    return on_intervention(new_record("L", "M01"), "counterexample")


def test_plan_shape() -> None:
    items = plan_assessment("M01")
    assert [i.kind for i in items] == ["transfer", "transfer", "transfer", "trap"]


def test_plan_avoids_seen_items() -> None:
    first = plan_assessment("M01")
    second = plan_assessment("M01", {i.item_id for i in first})
    assert second[0].item_id not in {i.item_id for i in first}
    assert second[-1].item_id != first[-1].item_id


def test_pass_first_item_fail_trap_not_resolved() -> None:
    items = plan_assessment("M01")
    answers = _answers(items, {items[0].item_id})
    result = evaluate_assessment(items, answers)
    assert result.item_correct[items[0].item_id]
    assert result.trap_passed is False
    assert not passes_reassessment(result)
    assert trap_misconceptions(items, answers) == ["M01"]
    record = on_assessment(_intervened(), result)
    assert record.state != MisconceptionState.resolved
    assert record.state == MisconceptionState.active


def test_all_transfer_pass_but_trap_fail_not_resolved() -> None:
    items = plan_assessment("M01")
    answers = _answers(items, {i.item_id for i in items if i.kind == "transfer"})
    record = on_assessment(_intervened(), evaluate_assessment(items, answers))
    assert record.state == MisconceptionState.active


def test_two_of_three_and_trap_pending_retest() -> None:
    items = plan_assessment("M01")
    answers = _answers(items, {items[0].item_id, items[1].item_id, items[3].item_id})
    result = evaluate_assessment(items, answers)
    assert passes_reassessment(result)
    record = on_assessment(_intervened(), result)
    assert record.state == MisconceptionState.intervened


def test_one_of_three_fails() -> None:
    items = plan_assessment("M01")
    answers = _answers(items, {items[0].item_id, items[3].item_id})
    assert not passes_reassessment(evaluate_assessment(items, answers))


def test_resolution_needs_retest() -> None:
    items = plan_assessment("M01")
    record = on_assessment(
        _intervened(), evaluate_assessment(items, _answers(items, {i.item_id for i in items}))
    )
    assert record.state == MisconceptionState.intervened
    retest = plan_retest("M01")
    failed = on_retest(record, evaluate_assessment([retest], {retest.item_id: retest.options[1]}))
    assert failed.state == MisconceptionState.active
    passed = on_retest(record, evaluate_assessment([retest], {retest.item_id: retest.correct_answer}))
    assert passed.state == MisconceptionState.resolved


def test_resolution_needs_low_posterior() -> None:
    record = _intervened().model_copy(update={"alpha": 50.0})
    retest = plan_retest("M01")
    passed = on_retest(record, evaluate_assessment([retest], {retest.item_id: retest.correct_answer}))
    assert passed.state != MisconceptionState.resolved
