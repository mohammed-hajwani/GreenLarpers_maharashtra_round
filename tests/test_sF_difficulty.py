import pytest

from relearn.adaptive.difficulty import band_for_mastery, coverage_report, decide_band, pick_template
from relearn.content import load_content
from relearn.learner.store import LearnerStore
from relearn.pipeline import Tutor
from relearn.schemas import LearnerResponse


def _hist(*correct, route="accept"):
    return [{"correct": c, "route": route} for c in correct]


@pytest.mark.parametrize(
    ("mastery", "band"), [(0.1, "easy"), (0.39, "easy"), (0.4, "medium"), (0.7, "medium"), (0.71, "hard")]
)
def test_mastery_bands(mastery: float, band: str) -> None:
    assert band_for_mastery(mastery) == band


def test_streak_steps_up_and_failures_step_down() -> None:
    assert decide_band(0.5, _hist(True, True, True), {}, "medium")[1] == "hard"
    assert decide_band(0.5, _hist(True, False, False), {}, "medium")[1] == "easy"
    assert decide_band(0.5, _hist(True, False), {}, "medium")[1] == "medium"


def test_active_misconception_caps_at_medium() -> None:
    _, band, reasons, factors = decide_band(0.9, [], {"M01": "active"}, "hard")
    assert band == "medium"
    assert factors["active_misconceptions"] == ["M01"]
    assert any("M01" in r for r in reasons)


def test_uncertain_diagnosis_blocks_step_up() -> None:
    hist = _hist(True, True) + _hist(True, route="uncertain")
    assert decide_band(0.5, hist, {}, "medium")[1] == "medium"


def test_change_limited_to_one_band() -> None:
    assert decide_band(0.9, [], {}, "easy")[1] == "medium"


def test_pick_template_avoids_recent_and_reports_gap() -> None:
    first, _ = pick_template("force_motion", "easy", [])
    second, _ = pick_template("force_motion", "easy", [first.template_id])
    assert first.template_id != second.template_id
    assert first.difficulty == "easy"
    template, gap = pick_template("free_fall", "hard", [])
    assert template.difficulty == "hard" and gap == ""


def test_coverage_report_lists_gaps() -> None:
    report = coverage_report()
    assert set(report["counts"]) == set(load_content().concepts)
    assert all(sum(v.values()) >= 4 for v in report["counts"].values())
    assert isinstance(report["gaps"], list)


def test_tutor_next_question_uses_stored_mastery(tmp_path) -> None:
    tutor = Tutor(LearnerStore(tmp_path / "f.db"))
    q, decision = tutor.next_question("L", "force_motion")
    assert decision.mastery == pytest.approx(0.5)
    assert decision.band == "medium"
    assert "50%" in decision.headline
    for _ in range(3):
        q, decision = tutor.next_question("L", "force_motion")
        d = tutor.submit(
            "L",
            q,
            LearnerResponse(question_id=q.question_id, answer="definitely wrong", working="a force keeps it moving"),
        )
        tutor.confirm("L", d, q)
    q, decision = tutor.next_question("L", "force_motion")
    stored = tutor.store.mastery("L", "force_motion").mean
    assert decision.mastery == pytest.approx(stored)
    assert decision.band == "easy"
    assert f"{round(100 * stored)}%" in decision.headline
    again_q, again = tutor.next_question("L", "force_motion")
    assert again.template_id == decision.template_id and again_q.stem == q.stem
