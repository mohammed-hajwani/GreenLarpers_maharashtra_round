import random

from relearn.diagnosis.diagnoser import diagnose
from relearn.diagnosis.disambiguator import run_probes
from relearn.models.baseline import BaselineModel
from relearn.schemas import Probe, Sample

NOISE = 0.1


def simulated_answer(rng: random.Random, probe: Probe, true_label: str, noise: float = NOISE) -> str:
    expected = probe.expected_answer_by_label.get(true_label)
    if expected is None or rng.random() < noise:
        return rng.choice(probe.options)
    return expected


def probing_lift(samples: list[Sample], model: BaselineModel, seed: int) -> dict:
    rng = random.Random(seed)
    subset = [s for s in samples if s.confusable_group]
    before = after = triggered = 0
    for s in subset:
        d = diagnose(s.question, s.response, model)
        before += d.top_labels[0][0] == s.misconception_label
        triggered += d.ambiguous
        label = s.misconception_label
        d2, _ = run_probes(d, lambda p, label=label: simulated_answer(rng, p, label))
        after += d2.top_labels[0][0] == s.misconception_label
    n = max(len(subset), 1)
    return {
        "n": len(subset),
        "probes_triggered": triggered,
        "accuracy_without_probing": before / n,
        "accuracy_with_probing": after / n,
        "lift_points": 100 * (after - before) / n,
    }
