from relearn.config import load_config
from relearn.schemas import AssessmentItem, AssessmentResult


def evaluate_assessment(items: list[AssessmentItem], answers: dict[str, str]) -> AssessmentResult:
    misconception = items[0].misconception
    correct = {i.item_id: answers.get(i.item_id, "").strip() == i.correct_answer for i in items}
    transfer = [i for i in items if i.kind == "transfer"]
    traps = [i for i in items if i.kind == "trap"]
    retests = [i for i in items if i.kind == "retest"]
    return AssessmentResult(
        misconception=misconception,
        transfer_correct=sum(correct[i.item_id] for i in transfer),
        transfer_total=len(transfer),
        trap_passed=all(correct[i.item_id] for i in traps) if traps else None,
        retest_passed=all(correct[i.item_id] for i in retests) if retests else None,
        item_correct=correct,
    )


def passes_reassessment(result: AssessmentResult) -> bool:
    need = load_config().assessment.transfer_pass_min
    return result.transfer_correct >= need and result.trap_passed is True


def trap_misconceptions(items: list[AssessmentItem], answers: dict[str, str]) -> list[str]:
    return [i.trap_answer_maps_to[answers[i.item_id]] for i in items if answers.get(i.item_id) in i.trap_answer_maps_to]
