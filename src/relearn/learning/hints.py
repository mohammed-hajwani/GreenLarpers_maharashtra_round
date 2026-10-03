import re

from relearn.content import load_content

SENTENCE = re.compile(r"(?<=[.!?])\s+")
BLOCKED = (
    "misconception",
    "strategy",
    "confidence",
    "probability",
    "related idea",
    "you answered",
    "your answer",
    "your reasoning",
    "your working",
    "you wrote",
)
GENERIC = "Here's a hint: picture the moment the question describes and list only the forces acting right then."


def _clean_sentences(text: str) -> list[str]:
    out = []
    for sentence in SENTENCE.split(text.strip()):
        low = sentence.lower()
        if not sentence or '"' in sentence or any(b in low for b in BLOCKED):
            continue
        out.append(sentence.strip())
    return out


def key_idea(mix_up: str | None) -> str:
    info = load_content().misconceptions.get(mix_up or "")
    return f"Key idea: {info.correct_concept}" if info else ""


def first_hint(intervention_text: str, mix_up: str) -> str:
    info = load_content().misconceptions.get(mix_up)
    concept = info.correct_concept if info else ""
    sentences = [s for s in _clean_sentences(intervention_text) if s != concept and concept not in s]
    if not sentences:
        return GENERIC
    return "Here's a hint: " + " ".join(sentences[:2])


def generic_hint() -> str:
    return GENERIC
