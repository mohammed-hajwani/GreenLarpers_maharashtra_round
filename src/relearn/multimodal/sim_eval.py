import random
import statistics

from relearn.content import load_content
from relearn.multimodal.modality import MODALITIES, available, choose_modality

ASSUMPTIONS = {
    "base_effectiveness": {"text": 0.35, "diagram": 0.42, "simulation": 0.48},
    "per_misconception_shift": "uniform(-0.2, 0.2) per modality, so the best modality differs by misconception",
    "per_learner_shift": "uniform(-0.15, 0.15) per modality (individual preference)",
    "clip": [0.05, 0.95],
    "max_interventions": 3,
    "label": "Simulated learners, not real students",
}
POLICIES = ("text_only", "fixed_rotation", "random", "adaptive")


def _population(rng: random.Random) -> dict[str, dict[str, float]]:
    base = ASSUMPTIONS["base_effectiveness"]
    return {
        m: {k: base[k] + rng.uniform(-0.2, 0.2) for k in available(m)} for m in sorted(load_content().misconceptions)
    }


def _choose(policy: str, m: str, tried: list[str], stats: dict, rng: random.Random, seed: str) -> str:
    options = available(m)
    if policy == "text_only":
        return "text"
    if policy == "fixed_rotation":
        return options[min(len(tried), len(options) - 1)]
    if policy == "random":
        fresh = [k for k in options if k not in tried] or options
        return rng.choice(fresh)
    pairs = {k: (v["s"], v["f"]) for k, v in stats.get(m, {}).items()}
    return choose_modality(m, pairs, tried, seed)[0]


def run_policy(policy: str, seed: int, learners: int = 3000) -> dict:
    rng = random.Random(seed)
    pop = _population(random.Random(seed * 7 + 1))
    stats: dict = {}
    first, within, used, late_first = [], [], [], []
    misconceptions = sorted(pop)
    for i in range(learners):
        m = rng.choice(misconceptions)
        learner = {k: min(0.95, max(0.05, p + rng.uniform(-0.15, 0.15))) for k, p in pop[m].items()}
        tried: list[str] = []
        resolved = False
        for _ in range(ASSUMPTIONS["max_interventions"]):
            k = _choose(policy, m, tried, stats, rng, f"{seed}-{i}-{len(tried)}")
            tried.append(k)
            ok = rng.random() < learner[k]
            cell = stats.setdefault(m, {}).setdefault(k, {"s": 0, "f": 0})
            cell["s" if ok else "f"] += 1
            if ok:
                resolved = True
                break
        first.append(resolved and len(tried) == 1)
        within.append(resolved)
        used.append(len(tried))
        if i >= learners * 2 // 3:
            late_first.append(resolved and len(tried) == 1)
    return {
        "first_try_resolution": statistics.mean(first),
        "first_try_resolution_last_third": statistics.mean(late_first),
        "resolved_within_3": statistics.mean(within),
        "mean_interventions": statistics.mean(used),
    }


def compare(seeds: tuple[int, ...] = (1, 2, 3, 4, 5), learners: int = 3000) -> dict:
    results = {}
    for policy in POLICIES:
        runs = [run_policy(policy, s, learners) for s in seeds]
        results[policy] = {
            key: {"mean": statistics.mean(r[key] for r in runs), "std": statistics.pstdev(r[key] for r in runs)}
            for key in runs[0]
        }
    return {
        "assumptions": ASSUMPTIONS,
        "learners_per_seed": learners,
        "seeds": list(seeds),
        "modalities": list(MODALITIES),
        "results": results,
    }
