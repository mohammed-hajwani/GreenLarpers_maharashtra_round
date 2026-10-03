import math

from relearn.config import load_config
from relearn.content import load_content
from relearn.diagnosis.routing import ACCEPT, PROBE, open_set_score, open_set_threshold, route_for, thresholds_for
from relearn.models.base import TextClassifier
from relearn.models.baseline import sample_text
from relearn.models.inference import (
    NONE,
    answer_key_verdict,
    apply_answer_key,
    energy,
    msp_novelty,
    working_conflict,
)
from relearn.models.loader import get_active_model
from relearn.models.registry import KIND_BY_NAME
from relearn.schemas import Diagnosis, LearnerResponse, Question


def entropy_bits(posterior: dict[str, float]) -> float:
    return float(-sum(p * math.log2(p) for p in posterior.values() if p > 0))


def finalize(
    posterior: dict[str, float] | list[tuple[str, float]],
    model_name: str = "",
    model_version: str = "",
    model_kind: str | None = None,
) -> Diagnosis:
    cfg = load_config()
    content = load_content()
    dist = dict(posterior)
    total = sum(dist.values()) or 1.0
    dist = {k: v / total for k, v in dist.items()}
    ranked = sorted(dist.items(), key=lambda x: -x[1])
    top_labels = ranked[: cfg.diagnosis.top_k]
    first, confidence = top_labels[0]
    kind = model_kind or KIND_BY_NAME.get(model_name)
    thresholds = thresholds_for(kind)
    is_correct = first == NONE and confidence >= thresholds["probe"]
    route = ACCEPT if is_correct else route_for(confidence, thresholds)
    lead = next((label for label, _ in top_labels if label != NONE), first)
    return Diagnosis(
        top_labels=top_labels,
        is_correct=is_correct,
        ambiguous=route != ACCEPT,
        confusable_group=content.group_of(lead),
        posterior=dist,
        confidence=confidence,
        entropy=entropy_bits(dist),
        route=route,
        model_name=model_name,
        model_version=model_version,
    )


def diagnose(question: Question, response: LearnerResponse, model: TextClassifier | None = None) -> Diagnosis:
    model = model or get_active_model().model
    if model is None:
        raise RuntimeError("no diagnosis model available")
    text = sample_text(question, response)
    raw = model.predict_proba([text], calibrated=False)[0]
    probs = model.predict_proba([text])[0]
    verdict = answer_key_verdict(question, response)
    limit = load_config().diagnosis.working_conflict_threshold
    conflict = working_conflict(probs, model.labels, verdict, limit)
    probs = apply_answer_key(probs, model.labels, verdict, limit)
    posterior = {label: float(p) for label, p in zip(model.labels, probs, strict=True)}
    diagnosis = finalize(posterior, model.name, model.version, model.kind)
    if conflict:
        diagnosis = diagnosis.model_copy(update={"route": PROBE, "ambiguous": True, "needs_probing": True})
    if open_set_score() == "energy":
        novelty = float(energy(model.logits([text]), load_config().open_set.energy_temperature)[0])
    else:
        novelty = msp_novelty(raw, model.labels)
    limit = open_set_threshold()
    unfamiliar = limit is not None and not diagnosis.is_correct and novelty > limit
    return diagnosis.model_copy(update={"novelty": novelty, "unfamiliar": unfamiliar})
