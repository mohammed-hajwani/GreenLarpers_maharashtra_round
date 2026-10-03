from relearn.config import load_config
from relearn.content import load_content
from relearn.models.baseline import BaselineModel, sample_text
from relearn.models.inference import NONE, answer_key_verdict, apply_answer_key, top_k
from relearn.models.loader import get_active_model
from relearn.schemas import Diagnosis, LearnerResponse, Question


def finalize(top_labels: list[tuple[str, float]]) -> Diagnosis:
    cfg = load_config()
    content = load_content()
    top_labels = sorted(top_labels, key=lambda x: -x[1])
    first = top_labels[0][0]
    group = content.group_of(first)
    rivals = [p for label, p in top_labels[1:] if group is not None and content.group_of(label) == group]
    ambiguous = bool(rivals) and top_labels[0][1] - rivals[0] < cfg.diagnosis.tau
    return Diagnosis(
        top_labels=top_labels, is_correct=first == NONE, ambiguous=ambiguous, confusable_group=group
    )


def diagnose(question: Question, response: LearnerResponse, model: BaselineModel | None = None) -> Diagnosis:
    model = model or get_active_model().model
    if model is None:
        raise RuntimeError("no diagnosis model available")
    probs = model.predict_proba([sample_text(question, response)])[0]
    probs = apply_answer_key(probs, model.labels, answer_key_verdict(question, response))
    return finalize(top_k(probs, model.labels, load_config().diagnosis.top_k))
