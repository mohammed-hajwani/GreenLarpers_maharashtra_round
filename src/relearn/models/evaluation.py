import numpy as np
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
)

from relearn.models.base import TextClassifier, softmax
from relearn.models.baseline import texts_of
from relearn.models.calibration import expected_calibration_error
from relearn.models.inference import answer_key_verdict, apply_answer_key
from relearn.schemas import Sample


def keyed(probs: np.ndarray, labels: list[str], samples: list[Sample]) -> np.ndarray:
    return np.stack(
        [apply_answer_key(probs[i], labels, answer_key_verdict(s.question, s.response)) for i, s in enumerate(samples)]
    )


def _scores(y: list[str], p: list[str], labels: list[str]) -> dict:
    precision, recall, f1, _ = precision_recall_fscore_support(y, p, labels=labels, average="macro", zero_division=0)
    return {
        "n": len(y),
        "accuracy": float(accuracy_score(y, p)) if y else 0.0,
        "macro_precision": float(precision),
        "macro_recall": float(recall),
        "macro_f1": float(f1),
    }


def evaluate_model(model: TextClassifier, samples: list[Sample]) -> dict:
    labels = model.labels
    y = [s.misconception_label for s in samples]
    targets = np.array([labels.index(v) for v in y])
    logits = model.logits(texts_of(samples))
    raw_uncal = softmax(logits)
    raw = softmax(logits / model.temperature)
    with_key = keyed(raw, labels, samples)
    p_raw = [labels[i] for i in raw.argmax(axis=1)]
    p_key = [labels[i] for i in with_key.argmax(axis=1)]
    precision, recall, f1, support = precision_recall_fscore_support(
        y, p_key, labels=labels, average=None, zero_division=0
    )
    conf_idx = [i for i, s in enumerate(samples) if s.confusable_group]
    return {
        "model_only": _scores(y, p_raw, labels),
        "with_answer_key": _scores(y, p_key, labels),
        "per_class": {
            label: {"precision": float(p), "recall": float(r), "f1": float(f), "support": int(n)}
            for label, p, r, f, n in zip(labels, precision, recall, f1, support, strict=True)
        },
        "confusable_subset": _scores([y[i] for i in conf_idx], [p_key[i] for i in conf_idx], labels),
        "ece_uncalibrated": expected_calibration_error(raw_uncal, targets),
        "ece_calibrated": expected_calibration_error(raw, targets),
        "classification_report": classification_report(y, p_key, labels=labels, zero_division=0),
        "confusion_matrix": confusion_matrix(y, p_key, labels=labels).tolist(),
        "labels": labels,
    }
