import random

from relearn.config import load_config
from relearn.content import load_content
from relearn.diagnosis.diagnoser import diagnose
from relearn.diagnosis.disambiguator import ProbeChoice, choose_probe, expected_information_gain, run_probes
from relearn.diagnosis.routing import ACCEPT
from relearn.models.base import TextClassifier
from relearn.schemas import Diagnosis, Probe, Sample


def simulated_answer(rng: random.Random, probe: Probe, true_label: str, noise: float) -> str:
    expected = probe.expected_answer_by_label.get(true_label)
    if expected is None or rng.random() < noise:
        return rng.choice(probe.options)
    return expected


def random_chooser(rng: random.Random):
    def choose(diagnosis: Diagnosis, used: set[str]) -> ProbeChoice | None:
        if (
            diagnosis.route == ACCEPT
            or diagnosis.is_correct
            or len(used) >= load_config().disambiguation.max_probes
        ):
            return None
        top = diagnosis.top_labels[0][0]
        pool = [
            p for p in load_content().probes if p.probe_id not in used and top in p.expected_answer_by_label
        ]
        if not pool:
            return None
        probe = rng.choice(pool)
        return ProbeChoice(probe, expected_information_gain(diagnosis.posterior, probe))

    return choose


def compare_probing(samples: list[Sample], model: TextClassifier, seed: int) -> dict:
    noise = load_config().disambiguation.answer_noise
    subset = [s for s in samples if s.confusable_group]
    diagnoses = [diagnose(s.question, s.response, model) for s in subset]
    results = {"n": len(subset), "routed_to_probe": sum(d.route != ACCEPT for d in diagnoses)}
    strategies = {"no_probe": None, "random_probe": "random", "information_gain_probe": "ig"}
    for name, kind in strategies.items():
        rng = random.Random(seed)
        chooser_rng = random.Random(seed + 1)
        correct = 0
        probes_used = 0
        entropy_drop = 0.0
        for s, d in zip(subset, diagnoses, strict=True):
            if kind is not None:
                chooser = random_chooser(chooser_rng) if kind == "random" else choose_probe
                label = s.misconception_label
                d, steps = run_probes(
                    d, lambda p, label=label, r=rng: simulated_answer(r, p, label, noise), chooser
                )
                probes_used += len(steps)
                entropy_drop += sum(st.information_gain for st in steps)
            correct += d.top_labels[0][0] == s.misconception_label
        n = max(len(subset), 1)
        results[name] = {
            "accuracy": correct / n,
            "probes_asked": probes_used,
            "mean_entropy_drop_bits_per_probe": entropy_drop / probes_used if probes_used else 0.0,
        }
    base = results["no_probe"]["accuracy"]
    for name in ("random_probe", "information_gain_probe"):
        results[name]["lift_points"] = 100 * (results[name]["accuracy"] - base)
    return results


def probing_lift(samples: list[Sample], model: TextClassifier, seed: int) -> dict:
    r = compare_probing(samples, model, seed)
    return {
        "n": r["n"],
        "probes_triggered": r["routed_to_probe"],
        "accuracy_without_probing": r["no_probe"]["accuracy"],
        "accuracy_with_probing": r["information_gain_probe"]["accuracy"],
        "lift_points": r["information_gain_probe"]["lift_points"],
    }
