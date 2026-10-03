import math
import random
from dataclasses import dataclass

from relearn.adaptive.difficulty import BAND_LEVELS, decide_band
from relearn.learner.mastery import item_evidence, practice_evidence, prior, probe_evidence, update
from relearn.schemas import Diagnosis

DIFFICULTY_OFFSET = {"easy": -0.15, "medium": 0.05, "hard": 0.25}
ASSUMPTIONS = {
    "skill_prior": "Beta(2, 2) latent skill per learner for the target concept",
    "holds_misconception_probability": 0.6,
    "p_correct": "sigmoid(6 * (skill - difficulty_offset)) * (0.45 if holding the misconception else 1.0)",
    "difficulty_offsets": DIFFICULTY_OFFSET,
    "diagnosis_confidence": "U(0.55, 0.95) when the wrong answer comes from the held misconception, else U(0.2, 0.6)",
    "probe": "asked when confidence < 0.7; answer matches the misconception with p=0.9 when held, 0.1 otherwise",
    "intervention": "after 2 diagnosed wrong answers; abandons the misconception with p=abandon_rate (U(0.2, 0.7))",
    "learning": "skill += learn_rate (U(0.01, 0.06)) after each correct answer, capped at 1",
    "reassessment": "after each intervention: 3 transfer + 1 trap, correctness from the same p_correct at medium",
    "horizon": "10 observed steps, outcome measured after 10 further steps",
    "mastery_target": 0.7,
}


@dataclass
class SimLearner:
    skill: float
    holds: bool
    abandon_rate: float
    learn_rate: float


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def sample_learner(rng: random.Random) -> SimLearner:
    return SimLearner(
        skill=rng.betavariate(2, 2),
        holds=rng.random() < ASSUMPTIONS["holds_misconception_probability"],
        abandon_rate=rng.uniform(0.2, 0.7),
        learn_rate=rng.uniform(0.01, 0.06),
    )


def p_correct(learner: SimLearner, band: str) -> float:
    p = _sigmoid(6 * (learner.skill - DIFFICULTY_OFFSET[band]))
    return p * (0.45 if learner.holds else 1.0)


def simulate(rng: random.Random, learner: SimLearner, steps: int) -> list[dict]:
    state = prior()
    events: list[dict] = []
    wrong_streak = 0
    previous = None
    for _ in range(steps):
        history = [
            {"correct": e["correct"], "route": e.get("route", "accept")} for e in events if e["kind"] == "practice"
        ]
        _, band, _, _ = decide_band(state.mean, history, {"M": "active"} if learner.holds else {}, previous)
        previous = band
        correct = rng.random() < p_correct(learner, band)
        from_misconception = not correct and learner.holds and rng.random() < 0.8
        confidence = rng.uniform(0.55, 0.95) if from_misconception else rng.uniform(0.2, 0.6)
        diagnosis = None if correct else Diagnosis(top_labels=[("M", confidence)], is_correct=False, ambiguous=False)
        state, rec = update(state, "c", "practice", "q", practice_evidence(correct, band, diagnosis))
        events.append(
            {
                "kind": "practice",
                "correct": correct,
                "difficulty": band,
                "confidence": None if correct else confidence,
                "route": "accept" if correct or confidence >= 0.7 else "probe",
                "mastery_after": rec.after,
            }
        )
        if correct:
            learner.skill = min(1.0, learner.skill + learner.learn_rate)
            wrong_streak = 0
            continue
        wrong_streak += 1
        if confidence < 0.7:
            consistent = rng.random() < (0.9 if learner.holds else 0.1)
            state, rec = update(state, "c", "probe", "p", probe_evidence(consistent, not consistent))
            events.append({"kind": "probe", "consistent": consistent, "mastery_after": rec.after})
        if wrong_streak >= 2:
            wrong_streak = 0
            if learner.holds and rng.random() < learner.abandon_rate:
                learner.holds = False
            events.append({"kind": "intervention", "mastery_after": state.mean})
            for kind in ("transfer", "transfer", "transfer", "trap"):
                ok = rng.random() < p_correct(learner, "medium")
                state, rec = update(state, "c", kind, "i", item_evidence(kind, ok))
                events.append({"kind": kind, "correct": ok, "mastery_after": rec.after})
    return events


def features(events: list[dict]) -> dict[str, float]:
    practice = [e for e in events if e["kind"] == "practice"]
    n = len(practice)
    correct = [e["correct"] for e in practice]
    recent = correct[-3:]
    conf = [e["confidence"] for e in practice if e.get("confidence") is not None]
    levels = [BAND_LEVELS[e["difficulty"]] for e in practice if e.get("difficulty") in BAND_LEVELS]
    masteries = [e["mastery_after"] for e in events if "mastery_after" in e]
    probes = [e for e in events if e["kind"] == "probe"]
    assessed = [e for e in events if e["kind"] in ("transfer", "trap")]
    return {
        "attempts": float(n),
        "accuracy": sum(correct) / n if n else 0.0,
        "recent_accuracy": sum(recent) / len(recent) if recent else 0.0,
        "misconception_rate": sum(1 for c in conf if c >= 0.55) / n if n else 0.0,
        "mean_wrong_confidence": sum(conf) / len(conf) if conf else 0.0,
        "mastery": masteries[-1] if masteries else 0.5,
        "mastery_slope": (masteries[-1] - masteries[0]) / len(masteries) if len(masteries) > 1 else 0.0,
        "probe_consistent_rate": sum(p["consistent"] for p in probes) / len(probes) if probes else 0.0,
        "interventions": float(sum(1 for e in events if e["kind"] == "intervention")),
        "assessment_accuracy": sum(e["correct"] for e in assessed) / len(assessed) if assessed else 0.0,
        "mean_difficulty": sum(levels) / len(levels) if levels else 2.0,
        "difficulty_trend": (levels[-1] - levels[0]) if len(levels) > 1 else 0.0,
    }


def prefix(events: list[dict], observed: int) -> list[dict]:
    seen = 0
    for i, e in enumerate(events):
        if e["kind"] == "practice":
            seen += 1
            if seen > observed:
                return events[:i]
    return events


def trajectory(rng: random.Random, observed: int = 10, horizon: int = 10) -> tuple[dict, int, int]:
    learner = sample_learner(rng)
    events = simulate(rng, learner, observed + horizon)
    final_mastery = [e["mastery_after"] for e in events if "mastery_after" in e][-1]
    return features(prefix(events, observed)), int(final_mastery >= ASSUMPTIONS["mastery_target"]), int(learner.holds)
