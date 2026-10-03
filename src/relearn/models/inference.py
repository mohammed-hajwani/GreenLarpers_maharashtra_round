import re

import numpy as np

from relearn.schemas import LearnerResponse, Question, QuestionType

NONE = "none"
SPACE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    return SPACE.sub(" ", text.strip().lower().rstrip("."))


def answer_key_verdict(question: Question, response: LearnerResponse) -> bool | None:
    if question.question_type == QuestionType.explanation:
        return None
    return _normalize(response.answer) == _normalize(question.correct_answer)


def apply_answer_key(probs: np.ndarray, labels: list[str], verdict: bool | None) -> np.ndarray:
    if verdict is None:
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


def top_k(probs: np.ndarray, labels: list[str], k: int) -> list[tuple[str, float]]:
    order = np.argsort(-probs)[:k]
    return [(labels[i], float(probs[i])) for i in order]
