import hashlib

from relearn.adaptive.difficulty import DifficultyDecision
from relearn.diagnosis.disambiguator import ProbeStep
from relearn.learner.mastery import MasteryUpdate
from relearn.schemas import AssessmentResult, Diagnosis, LearnerRecord, LearnerResponse, Question

RESOLUTION_RULE = "resolved only after >=2/3 transfer correct, trap passed, and a delayed retest passed"


def _digest(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def _diag(d: Diagnosis) -> dict:
    return {
        "predicted": d.top_labels[0][0],
        "top_predictions": d.top_labels,
        "confidence": d.confidence,
        "route": d.route,
        "entropy": d.entropy,
        "is_correct": d.is_correct,
    }


def _probe(s: ProbeStep) -> dict:
    return {
        "probe_id": s.probe_id,
        "expected_information_gain": s.expected_gain,
        "runners_up": s.runners_up,
        "answer": s.answer,
        "entropy_before": s.entropy_before,
        "entropy_after": s.entropy_after,
        "information_gain": s.information_gain,
        "confidence_before": s.confidence_before,
        "confidence_after": s.confidence_after,
        "mastery": s.mastery.to_dict() if s.mastery else None,
    }


def _decision(d: DifficultyDecision | None) -> dict | None:
    if d is None:
        return None
    return {
        "concept": d.concept,
        "concept_name": d.concept_name,
        "mastery": d.mastery,
        "band": d.band,
        "headline": d.headline,
        "reasons": d.reasons,
    }


def practice_trace(
    question: Question,
    response: LearnerResponse,
    initial: Diagnosis,
    final: Diagnosis,
    steps: list[ProbeStep],
    record: LearnerRecord | None,
    mastery: MasteryUpdate | None,
    decision: DifficultyDecision | None,
    explanation: dict,
    thresholds: dict,
) -> tuple[str, dict]:
    trace = {
        "question_id": question.question_id,
        "question": question.stem,
        "answer": response.answer,
        "working": response.working,
        "model_name": final.model_name,
        "model_version": final.model_version,
        "thresholds": thresholds,
        "initial": _diag(initial),
        "probes": [_probe(s) for s in steps],
        "final": _diag(final),
        "misconception_state": record.state.value if record else None,
        "mastery": mastery.to_dict() if mastery else None,
        "next_difficulty": _decision(decision),
        "explanation": explanation,
    }
    return _digest(f"{question.stem}|{response.answer}|{response.working}"), trace


def assessment_trace(
    kind: str,
    misconception: str,
    before: LearnerRecord,
    after: LearnerRecord,
    result: AssessmentResult,
    updates: list[MasteryUpdate],
) -> tuple[str, dict]:
    trace = {
        "misconception": misconception,
        "state_before": before.state.value,
        "state_after": after.state.value,
        "transfer": f"{result.transfer_correct}/{result.transfer_total}",
        "trap_passed": result.trap_passed,
        "retest_passed": result.retest_passed,
        "items": result.item_correct,
        "mastery_updates": [u.to_dict() for u in updates],
        "resolution_rule": RESOLUTION_RULE,
    }
    return _digest(f"{kind}|{misconception}|{sorted(result.item_correct.items())}"), trace
