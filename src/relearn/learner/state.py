from datetime import UTC, datetime

from relearn.assessment.evaluator import passes_reassessment
from relearn.config import load_config
from relearn.schemas import AssessmentResult, LearnerRecord, MisconceptionState

S = MisconceptionState


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def new_record(learner_id: str, misconception: str) -> LearnerRecord:
    lc = load_config().learner
    return LearnerRecord(
        learner_id=learner_id,
        misconception=misconception,
        state=S.unseen,
        alpha=lc.prior_alpha,
        beta=lc.prior_beta,
        strategies_tried=[],
        last_updated=now(),
    )


def posterior_mean(record: LearnerRecord) -> float:
    return record.alpha / (record.alpha + record.beta)


def on_diagnosis(record: LearnerRecord, confidence: float) -> LearnerRecord:
    cfg = load_config()
    r = record.model_copy(deep=True)
    r.alpha += confidence * cfg.learner.fail_alpha_increment
    confident = confidence >= cfg.diagnosis.confident_threshold
    if r.state == S.unseen and confident:
        r.state = S.active
    elif r.state == S.resolved:
        r.state = S.relapsed
    elif r.state == S.intervened:
        r.state = S.active
    r.last_updated = now()
    return r


def on_intervention(record: LearnerRecord, strategy: str) -> LearnerRecord:
    r = record.model_copy(deep=True)
    if r.state in (S.active, S.relapsed, S.unseen):
        r.state = S.intervened
    if strategy not in r.strategies_tried:
        r.strategies_tried.append(strategy)
    r.last_updated = now()
    return r


def on_assessment(record: LearnerRecord, result: AssessmentResult) -> LearnerRecord:
    lc = load_config().learner
    r = record.model_copy(deep=True)
    passed = sum(result.item_correct.values())
    failed = len(result.item_correct) - passed
    r.beta += passed * lc.pass_beta_increment
    r.alpha += failed * lc.fail_alpha_increment
    if result.trap_passed is False:
        r.state = S.relapsed if r.state == S.resolved else S.active
    elif not passes_reassessment(result) and result.retest_passed is None:
        r.state = S.active
    r.last_updated = now()
    return r


def on_retest(record: LearnerRecord, result: AssessmentResult) -> LearnerRecord:
    r = on_assessment(record, result)
    limit = load_config().assessment.resolved_posterior_max
    if result.retest_passed and r.state == S.intervened and posterior_mean(r) < limit:
        r.state = S.resolved
    elif result.retest_passed is False:
        r.state = S.relapsed if record.state == S.resolved else S.active
    return r
