import json
import math

import pytest

from relearn.config import load_config
from relearn.content import load_content
from relearn.diagnosis.diagnoser import finalize
from relearn.diagnosis.disambiguator import (
    bayes_update,
    choose_probe,
    expected_information_gain,
    likelihood,
    rank_probes,
    run_probes,
)

PROBES = {p.probe_id: p for p in load_content().probes}


def test_likelihood_uses_noise() -> None:
    p = PROBES["p_cg2_01"]
    noise = load_config().disambiguation.answer_noise
    expected = p.expected_answer_by_label["M01"]
    other = next(o for o in p.options if o != expected)
    assert likelihood(p, "M01", expected) == pytest.approx(1 - noise)
    assert likelihood(p, "M01", other) == pytest.approx(noise / (len(p.options) - 1))
    assert likelihood(p, "M02", expected) == pytest.approx(1 / len(p.options))


def test_bayes_update_normalizes_and_shifts() -> None:
    p = PROBES["p_cg2_01"]
    post = bayes_update({"M01": 0.5, "M09": 0.5}, p, p.expected_answer_by_label["M09"])
    assert sum(post.values()) == pytest.approx(1.0)
    assert post["M09"] > 0.9


def test_information_gain_prefers_separating_probe() -> None:
    posterior = {"M01": 0.5, "M09": 0.5}
    separating = expected_information_gain(posterior, PROBES["p_cg2_01"])
    irrelevant = expected_information_gain(posterior, PROBES["p_cg4_01"])
    assert separating > 0.5
    assert irrelevant == pytest.approx(0.0, abs=1e-9)
    assert separating <= math.log2(2) + 1e-9


def test_choice_logs_runners_up_and_respects_route() -> None:
    d = finalize({"M01": 0.5, "M09": 0.45, "M12": 0.05})
    choice = choose_probe(d)
    assert choice is not None
    assert choice.probe.confusable_group == "CG2"
    ranked = rank_probes(d)
    assert choice.expected_gain == pytest.approx(ranked[0][1])
    assert all(g <= choice.expected_gain + 1e-12 for _, g in choice.runners_up)
    assert choose_probe(finalize({"M01": 0.95, "M09": 0.05})) is None


def test_probe_loop_logs_entropy_and_caps() -> None:
    d = finalize({"M01": 0.34, "M09": 0.33, "M12": 0.33})
    final, steps = run_probes(d, lambda p: p.expected_answer_by_label.get("M12", p.options[0]))
    assert 1 <= len(steps) <= load_config().disambiguation.max_probes
    first = steps[0]
    assert first.entropy_before == pytest.approx(d.entropy)
    assert first.information_gain == pytest.approx(first.entropy_before - first.entropy_after)
    assert final.top_labels[0][0] == "M12"


def test_simulation_report_present() -> None:
    m = json.loads((load_config().path("reports_dir") / "metrics.json").read_text(encoding="utf-8"))
    results = m["probing"]["results"]
    for kind in results.values():
        for split in kind.values():
            assert {"no_probe", "random_probe", "information_gain_probe"} <= set(split)
            assert isinstance(split["information_gain_beats_random"], bool)
