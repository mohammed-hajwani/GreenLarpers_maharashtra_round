from relearn.learner.state import on_assessment, on_retest
from relearn.learner.store import LearnerStore
from relearn.schemas import AssessmentResult, LearnerRecord


def update_learner(store: LearnerStore, learner_id: str, misconception: str, result: AssessmentResult) -> LearnerRecord:
    record = store.get(learner_id, misconception)
    record = on_retest(record, result) if result.retest_passed is not None else on_assessment(record, result)
    store.put(record)
    return record
