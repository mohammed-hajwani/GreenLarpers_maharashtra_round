import re

import numpy as np
from scipy.special import logsumexp

from relearn.schemas import LearnerResponse, Question, QuestionType

NONE = "none"
SPACE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    return SPACE.sub(" ", text.strip().lower().rstrip("."))


def answer_key_verdict(question: Question, response: LearnerResponse) -> bool | None:
    if question.question_type == QuestionType.explanation:
        return None
    return _normalize(response.answer) == _normalize(question.correct_answer)


def working_conflict(probs: np.ndarray, labels: list[str], verdict: bool | None, threshold: float | None) -> bool:
    if not verdict or threshold is None:
        return False
    return max(float(p) for label, p in zip(labels, probs, strict=True) if label != NONE) >= threshold


def apply_answer_key(
    probs: np.ndarray, labels: list[str], verdict: bool | None, conflict_threshold: float | None = None
) -> np.ndarray:
    if verdict is None or working_conflict(probs, labels, verdict, conflict_threshold):
        return probs
    out = probs.copy()
    none_idx = labels.index(NONE)
    if verdict:
        out[:] = 0.0
        out[none_idx] = 1.0
        return out
    out[none_idx] = 0.0
    total = out.sum()
    return out / total if total > 0 else probs


def energy(logits: np.ndarray, temperature: float) -> np.ndarray:
    return -temperature * logsumexp(logits / temperature, axis=1)


def msp_novelty(raw_probs: np.ndarray, labels: list[str]) -> float:
    return 1.0 - max(float(p) for label, p in zip(labels, raw_probs, strict=True) if label != NONE)


def top_k(probs: np.ndarray, labels: list[str], k: int) -> list[tuple[str, float]]:
    order = np.argsort(-probs)[:k]
    return [(labels[i], float(probs[i])) for i in order]
