from relearn.app.demo import load_script, run_demo
from relearn.learner.store import LearnerStore
from relearn.models.loader import get_active_model
from relearn.pipeline import Tutor


def test_scripted_end_to_end(tmp_path) -> None:
    tutor = Tutor(LearnerStore(tmp_path / "demo.db"), get_active_model().model)
    steps = run_demo(tutor)
    kinds = [s["kind"] for s in steps]
    assert kinds[0] == "diagnosis"
    assert steps[0]["data"]["ambiguous"]
    assert "probe" in kinds
    probe = next(s for s in steps if s["kind"] == "probe")
    assert probe["data"]["top_labels"][0][0] == "M01"
    interventions = [s for s in steps if s["kind"] == "intervention"]
    assert len(interventions) == 2
    assert interventions[0]["data"]["strategy"] != interventions[1]["data"]["strategy"]
    first, second = [s["data"] for s in steps if s["kind"] == "assessment"]
    assert first["items"][0]["correct"]
    assert first["trap_passed"] is False
    assert first["state"] != "resolved"
    assert second["trap_passed"] is True
    assert second["state"] == "intervened"
    retest = next(s for s in steps if s["kind"] == "retest")
    assert retest["data"]["state"] == "resolved"
    profile = steps[-1]["data"]["rows"]
    assert any(r["misconception"] == "M01" and r["state"] == "resolved" for r in profile)


def test_recorded_steps_match_kinds() -> None:
    recorded = load_script()["recorded_steps"]
    assert recorded, "run scripts/record_demo.py"
    assert recorded[-1]["kind"] == "profile"
