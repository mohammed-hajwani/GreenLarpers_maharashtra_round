import random

from relearn.multimodal.diagrams import load_visuals

MODALITIES = ("text", "diagram", "simulation")
LABELS = {"text": "Explanation", "diagram": "Picture it", "simulation": "Try it yourself"}


def available(misconception: str) -> list[str]:
    spec = load_visuals().get(misconception, {})
    out = ["text"]
    if spec.get("diagram"):
        out.append("diagram")
    if spec.get("simulation"):
        out.append("simulation")
    return out


def choose_modality(
    misconception: str, stats: dict[str, tuple[int, int]], tried: list[str], seed: str
) -> tuple[str, dict[str, float]]:
    options = available(misconception)
    fresh = [m for m in options if m not in tried] or options
    rng = random.Random(seed)
    draws = {}
    for m in fresh:
        success, failure = stats.get(m, (0, 0))
        draws[m] = rng.betavariate(1 + success, 1 + failure)
    best = max(draws, key=lambda m: (draws[m], -MODALITIES.index(m)))
    return best, draws
