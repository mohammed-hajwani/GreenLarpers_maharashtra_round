import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score

from relearn.models.baseline import BaselineModel, texts_of
from relearn.models.calibration import expected_calibration_error
from relearn.models.inference import answer_key_verdict, apply_answer_key
from relearn.schemas import Sample


def keyed_probs(model: BaselineModel, samples: list[Sample]) -> np.ndarray:
    raw = model.predict_proba(texts_of(samples))
    return np.stack(
        [
            apply_answer_key(raw[i], model.labels, answer_key_verdict(s.question, s.response))
            for i, s in enumerate(samples)
        ]
    )


def _scores(y: list[str], p: list[str], labels: list[str]) -> dict:
    return {
        "n": len(y),
        "accuracy": float(accuracy_score(y, p)),
        "macro_f1": float(f1_score(y, p, labels=labels, average="macro", zero_division=0)),
    }


def evaluate_model(model: BaselineModel, samples: list[Sample]) -> dict:
    labels = model.labels
    y = [s.misconception_label for s in samples]
    targets = np.array([labels.index(v) for v in y])
    raw = model.predict_proba(texts_of(samples))
    keyed = keyed_probs(model, samples)
    p_raw = [labels[i] for i in raw.argmax(axis=1)]
    p_key = [labels[i] for i in keyed.argmax(axis=1)]
    per_class = f1_score(y, p_key, labels=labels, average=None, zero_division=0)
    conf_idx = [i for i, s in enumerate(samples) if s.confusable_group]
    return {
        "model_only": _scores(y, p_raw, labels),
        "with_answer_key": _scores(y, p_key, labels),
        "per_class_f1": {label: float(v) for label, v in zip(labels, per_class, strict=True)},
        "confusable_subset": _scores([y[i] for i in conf_idx], [p_key[i] for i in conf_idx], labels),
        "ece": expected_calibration_error(raw, targets),
        "confusion_matrix": confusion_matrix(y, p_key, labels=labels).tolist(),
        "labels": labels,
    }
