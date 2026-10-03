from dataclasses import dataclass, field

from relearn.config import load_config
from relearn.content import load_content
from relearn.diagnosis.diagnoser import entropy_bits, finalize
from relearn.diagnosis.routing import ACCEPT
from relearn.schemas import Diagnosis, Probe


@dataclass
class ProbeChoice:
    probe: Probe
    expected_gain: float
    runners_up: list[tuple[str, float]] = field(default_factory=list)


@dataclass
class ProbeStep:
    probe_id: str
    answer: str
    expected_gain: float
    runners_up: list[tuple[str, float]]
    entropy_before: float
    entropy_after: float
    confidence_before: float
    confidence_after: float
    top_before: list[tuple[str, float]]
    top_after: list[tuple[str, float]]
    mastery: object = None

    @property
    def information_gain(self) -> float:
        return self.entropy_before - self.entropy_after


def _noise() -> float:
    return load_config().disambiguation.answer_noise


def likelihood(probe: Probe, label: str, answer: str, noise: float | None = None) -> float:
    noise = _noise() if noise is None else noise
    n = len(probe.options)
    expected = probe.expected_answer_by_label.get(label)
    if expected is None:
        return 1.0 / n
    return 1.0 - noise if answer == expected else noise / (n - 1)


def _posterior(diagnosis: Diagnosis) -> dict[str, float]:
    return dict(diagnosis.posterior) if diagnosis.posterior else dict(diagnosis.top_labels)


def floored(posterior: dict[str, float]) -> dict[str, float]:
    floor = load_config().disambiguation.prior_floor
    raised = {label: max(p, floor) for label, p in posterior.items()}
    total = sum(raised.values()) or 1.0
    return {label: p / total for label, p in raised.items()}


def bayes_update(posterior: dict[str, float], probe: Probe, answer: str) -> dict[str, float]:
    updated = {label: p * likelihood(probe, label, answer) for label, p in floored(posterior).items()}
    total = sum(updated.values()) or 1.0
    return {label: p / total for label, p in updated.items()}


def expected_information_gain(posterior: dict[str, float], probe: Probe) -> float:
    posterior = floored(posterior)
    h_before = entropy_bits(posterior)
    expected_after = 0.0
    for option in probe.options:
        p_option = sum(p * likelihood(probe, label, option) for label, p in posterior.items())
        if p_option > 0:
            expected_after += p_option * entropy_bits(bayes_update(posterior, probe, option))
    return h_before - expected_after


def rank_probes(diagnosis: Diagnosis, used: set[str] | None = None) -> list[tuple[Probe, float]]:
    used = used or set()
    posterior = _posterior(diagnosis)
    scored = [(p, expected_information_gain(posterior, p)) for p in load_content().probes if p.probe_id not in used]
    return sorted(scored, key=lambda x: (-x[1], x[0].probe_id))


def choose_probe(diagnosis: Diagnosis, used: set[str] | None = None) -> ProbeChoice | None:
    d = load_config().disambiguation
    settled = diagnosis.route == ACCEPT and not diagnosis.needs_probing
    if settled or diagnosis.is_correct or len(used or ()) >= d.max_probes:
        return None
    ranked = rank_probes(diagnosis, used)
    if not ranked or ranked[0][1] < d.min_expected_gain:
        return None
    runners = [(p.probe_id, round(g, 4)) for p, g in ranked[1:4]]
    return ProbeChoice(ranked[0][0], ranked[0][1], runners)


def select_probe(diagnosis: Diagnosis, used: set[str] | None = None) -> Probe | None:
    choice = choose_probe(diagnosis, used)
    return choice.probe if choice else None


def update_with_probe(diagnosis: Diagnosis, probe: Probe, answer: str) -> Diagnosis:
    posterior = bayes_update(_posterior(diagnosis), probe, answer)
    return finalize(posterior, diagnosis.model_name, diagnosis.model_version)


def apply_probe(diagnosis: Diagnosis, choice: ProbeChoice, answer: str) -> tuple[Diagnosis, ProbeStep]:
    after = update_with_probe(diagnosis, choice.probe, answer)
    step = ProbeStep(
        probe_id=choice.probe.probe_id,
        answer=answer,
        expected_gain=choice.expected_gain,
        runners_up=choice.runners_up,
        entropy_before=diagnosis.entropy,
        entropy_after=after.entropy,
        confidence_before=diagnosis.confidence,
        confidence_after=after.confidence,
        top_before=diagnosis.top_labels,
        top_after=after.top_labels,
    )
    return after, step


def run_probes(diagnosis: Diagnosis, answer_fn, chooser=None) -> tuple[Diagnosis, list[ProbeStep]]:
    chooser = chooser or choose_probe
    used: set[str] = set()
    steps: list[ProbeStep] = []
    while (choice := chooser(diagnosis, used)) is not None:
        used.add(choice.probe.probe_id)
        diagnosis, step = apply_probe(diagnosis, choice, answer_fn(choice.probe))
        steps.append(step)
    return diagnosis, steps
