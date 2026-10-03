from functools import lru_cache

import yaml

from relearn.config import ROOT
from relearn.content import load_content
from relearn.data.generator import make_question
from relearn.diagnosis.diagnoser import diagnose
from relearn.diagnosis.screening import MIN_REASONING_WORDS
from relearn.models.base import TextClassifier
from relearn.schemas import LearnerResponse, Question

CLEAR_BELOW = 0.5
TRICKY_FROM = 0.75
MIN_WORDS = 6


@lru_cache(maxsize=16)
def anchor_question(misconception: str) -> Question:
    content = load_content()
    pool = [t for t in content.templates if t.primary == misconception]
    template = next((t for t in pool if t.question_type.value == "explanation"), pool[0])
    return make_question(template, {k: v[0] for k, v in template.params.items()})


def score_explanation(model: TextClassifier, misconception: str, text: str) -> tuple[str, float]:
    if len(text.split()) < max(MIN_WORDS, MIN_REASONING_WORDS):
        return "needs_more", 0.0
    question = anchor_question(misconception)
    response = LearnerResponse(question_id=question.question_id, answer="", working=text)
    prob = diagnose(question, response, model).posterior.get(misconception, 0.0)
    if prob >= TRICKY_FROM:
        return "tricky", prob
    if prob >= CLEAR_BELOW:
        return "partly", prob
    return "clear", prob


def evaluate_explanations(model: TextClassifier) -> dict:
    with (ROOT / "content" / "explain_eval.yaml").open(encoding="utf-8") as handle:
        rows = yaml.safe_load(handle)["explanations"]
    counts = {"holds": {"tricky": 0, "partly": 0, "clear": 0}, "sound": {"tricky": 0, "partly": 0, "clear": 0}}
    details = []
    for row in rows:
        status, prob = score_explanation(model, row["misconception"], row["text"])
        counts["holds" if row["holds"] else "sound"][status] += 1
        details.append({**row, "status": status, "probability": round(prob, 3)})
    holds = sum(counts["holds"].values())
    sound = sum(counts["sound"].values())
    return {
        "provenance": "hand-written by the project team: per misconception, 1 sound and 1 holding explanation",
        "note": "bands were picked from a 6-pair pilot that overlaps this set",
        "bands": {"clear_below": CLEAR_BELOW, "tricky_from": TRICKY_FROM},
        "counts": counts,
        "holding_caught_as_tricky": counts["holds"]["tricky"] / holds,
        "holding_not_cleared": (holds - counts["holds"]["clear"]) / holds,
        "sound_accepted_as_clear": counts["sound"]["clear"] / sound,
        "sound_wrongly_tricky": counts["sound"]["tricky"] / sound,
        "details": details,
    }
