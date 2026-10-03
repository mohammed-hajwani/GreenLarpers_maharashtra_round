import pytest

from relearn.config import load_config
from relearn.content import load_content
from relearn.data.pipeline import build_splits
from relearn.diagnosis.diagnoser import diagnose, finalize
from relearn.diagnosis.disambiguator import run_probes, select_probe, update_with_probe
from relearn.diagnosis.probe_eval import probing_lift
from relearn.models.loader import get_active_model


def test_ambiguous_flag() -> None:
    d = finalize([("M01", 0.45), ("M09", 0.40), ("M02", 0.15)])
    assert d.ambiguous and d.confusable_group == "CG2"
    assert finalize([("M01", 0.45), ("M02", 0.40), ("M03", 0.15)]).route == "uncertain"
    assert not finalize([("M01", 0.80), ("M09", 0.15), ("M02", 0.05)]).ambiguous


def test_probe_selection_and_update() -> None:
    d = finalize([("M01", 0.45), ("M09", 0.40), ("M02", 0.15)])
    probe = select_probe(d)
    assert probe is not None
    expected = probe.expected_answer_by_label
    assert expected["M01"] != expected["M09"]
    updated = update_with_probe(d, probe, expected["M09"])
    assert updated.top_labels[0][0] == "M09"
    assert abs(sum(p for _, p in updated.top_labels) - 1.0) < 1e-9


def test_probe_loop_capped() -> None:
    d = finalize([("M01", 0.34), ("M09", 0.33), ("M12", 0.33)])
    _, trail = run_probes(d, lambda p: "nonsense")
    assert len(trail) <= load_config().disambiguation.max_probes


def test_diagnose_runs() -> None:
    c = load_content()
    t = c.templates[0]
    from relearn.data.generator import make_question
    from relearn.schemas import LearnerResponse

    q = make_question(t, {k: v[0] for k, v in t.params.items()})
    d = diagnose(q, LearnerResponse(question_id=q.question_id, answer=q.correct_answer, working=""))
    assert d.is_correct


@pytest.mark.parametrize("split", ["val", "test"])
def test_probing_does_not_hurt(split: str) -> None:
    cfg = load_config()
    splits = build_splits(cfg)
    result = probing_lift(splits[split], get_active_model().model, cfg.seed)
    assert result["lift_points"] >= 0
