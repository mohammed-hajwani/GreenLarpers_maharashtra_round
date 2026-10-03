from relearn.config import load_config
from relearn.content import load_content
from relearn.diagnosis.diagnoser import finalize
from relearn.schemas import Diagnosis, Probe


def _separates(probe: Probe, a: str, b: str) -> bool:
    expected = probe.expected_answer_by_label
    return a in expected and b in expected and expected[a] != expected[b]


def select_probe(diagnosis: Diagnosis, used: set[str] | None = None) -> Probe | None:
    if not diagnosis.ambiguous or diagnosis.confusable_group is None:
        return None
    used = used or set()
    content = load_content()
    first = diagnosis.top_labels[0][0]
    second = next(
        (
            label
            for label, _ in diagnosis.top_labels[1:]
            if content.group_of(label) == diagnosis.confusable_group
        ),
        None,
    )
    if second is None:
        return None
    candidates = [
        p
        for p in content.probes
        if p.confusable_group == diagnosis.confusable_group and p.probe_id not in used
    ]
    separating = [p for p in candidates if _separates(p, first, second)]
    pool = separating or candidates
    return pool[0] if pool else None


def update_with_probe(diagnosis: Diagnosis, probe: Probe, answer: str) -> Diagnosis:
    d = load_config().disambiguation
    updated = []
    for label, p in diagnosis.top_labels:
        expected = probe.expected_answer_by_label.get(label)
        updated.append((label, p * (d.match_likelihood if expected == answer else d.mismatch_likelihood)))
    total = sum(p for _, p in updated) or 1.0
    return finalize([(label, p / total) for label, p in updated])


def run_probes(diagnosis: Diagnosis, answer_fn) -> tuple[Diagnosis, list[tuple[Probe, str]]]:
    max_probes = load_config().disambiguation.max_probes
    used: set[str] = set()
    trail: list[tuple[Probe, str]] = []
    while diagnosis.ambiguous and len(trail) < max_probes:
        probe = select_probe(diagnosis, used)
        if probe is None:
            break
        answer = answer_fn(probe)
        used.add(probe.probe_id)
        trail.append((probe, answer))
        diagnosis = update_with_probe(diagnosis, probe, answer)
    return diagnosis, trail
