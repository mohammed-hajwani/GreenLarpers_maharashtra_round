from dataclasses import dataclass, field

from relearn.config import load_config
from relearn.content import TemplateSpec, load_content
from relearn.data.generator import make_question
from relearn.schemas import Question

BANDS = ["easy", "medium", "hard"]
ACTIVE_STATES = {"active", "intervened", "relapsed"}


@dataclass
class DifficultyDecision:
    concept: str
    concept_name: str
    mastery: float
    base_band: str
    band: str
    reasons: list[str] = field(default_factory=list)
    factors: dict = field(default_factory=dict)
    template_id: str = ""
    coverage_gap: str = ""

    @property
    def headline(self) -> str:
        return (
            f"Next question selected because your mastery of {self.concept_name} is currently "
            f"{round(100 * self.mastery)}%."
        )


def band_for_mastery(mastery: float) -> str:
    d = load_config().difficulty
    if mastery < d.easy_below:
        return "easy"
    if mastery <= d.hard_above:
        return "medium"
    return "hard"


def _shift(band: str, step: int) -> str:
    return BANDS[min(max(BANDS.index(band) + step, 0), len(BANDS) - 1)]


def decide_band(
    mastery: float,
    recent: list[dict],
    misconception_states: dict[str, str],
    previous_band: str | None,
) -> tuple[str, str, list[str], dict]:
    window = load_config().difficulty.recent_window
    base = band_for_mastery(mastery)
    band = base
    reasons = [f"mastery {mastery:.0%} maps to the {base} band"]
    last = recent[-window:]
    correct = [r["correct"] for r in last]
    if len(last) == window and all(correct):
        band = _shift(band, 1)
        reasons.append(f"last {window} answers in this concept were correct, so step up")
    elif len(correct) >= 2 and not any(correct[-2:]):
        band = _shift(band, -1)
        reasons.append("last 2 answers in this concept were wrong, so step down")
    active = sorted(m for m, s in misconception_states.items() if s in ACTIVE_STATES)
    if active and band == "hard":
        band = "medium"
        reasons.append(f"unresolved misconception {', '.join(active)} caps difficulty at medium")
    low_conf = [r for r in last if r.get("route") == "uncertain"]
    if low_conf and BANDS.index(band) > BANDS.index(base):
        band = base
        reasons.append("a recent diagnosis was uncertain, so no step up")
    if previous_band and abs(BANDS.index(band) - BANDS.index(previous_band)) > 1:
        band = _shift(previous_band, 1 if BANDS.index(band) > BANDS.index(previous_band) else -1)
        reasons.append(f"limited to one band away from the previous {previous_band} question")
    factors = {
        "mastery": mastery,
        "recent_correct": correct,
        "active_misconceptions": active,
        "recent_uncertain": len(low_conf),
        "previous_band": previous_band,
    }
    return base, band, reasons, factors


def pick_template(concept: str, band: str, recent_template_ids: list[str]) -> tuple[TemplateSpec, str]:
    content = load_content()
    pool = [t for t in content.templates if content.concept_of(t.primary) == concept]
    gap = ""
    for distance in range(len(BANDS)):
        candidates = [t for t in pool if abs(BANDS.index(t.difficulty) - BANDS.index(band)) == distance]
        if candidates:
            if distance:
                gap = f"no {band} template for this concept; used nearest band {candidates[0].difficulty}"
            break
    usage = {tid: i for i, tid in enumerate(recent_template_ids)}
    candidates.sort(key=lambda t: (usage.get(t.template_id, -1), t.template_id))
    return candidates[0], gap


def instantiate(template: TemplateSpec, attempt_index: int) -> Question:
    keys = list(template.params)
    params = {k: template.params[k][(attempt_index + i) % len(template.params[k])] for i, k in enumerate(keys)}
    return make_question(template, params)


def coverage_report() -> dict:
    content = load_content()
    need = load_config().difficulty.min_templates_per_band
    table = {}
    gaps = []
    for concept in content.concepts.values():
        counts = {b: 0 for b in BANDS}
        for t in content.templates:
            if content.concept_of(t.primary) == concept.id:
                counts[t.difficulty] += 1
        table[concept.id] = counts
        gaps.extend(f"{concept.name}: {b} has {n} template(s), want {need}" for b, n in counts.items() if n < need)
    return {"counts": table, "gaps": gaps, "min_templates_per_band": need}
