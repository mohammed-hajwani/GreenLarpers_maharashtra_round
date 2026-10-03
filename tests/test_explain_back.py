import json

import pytest

from relearn import services as svc
from relearn.config import ROOT
from relearn.learner.store import LearnerStore
from relearn.learning.explain import score_explanation
from relearn.learning.flow import LessonEngine
from relearn.learning.guided import DEMO_EXPLANATION, STEPS, start_demo
from relearn.models.loader import get_active_model
from relearn.pipeline import Tutor

GOOD = DEMO_EXPLANATION
BAD = "Yes, you always need a force pushing it forward or it will slow down and stop."


@pytest.fixture
def tutor(tmp_path) -> Tutor:
    return Tutor(LearnerStore(tmp_path / "e.db"), get_active_model().model)


def test_scorer_bands(tutor) -> None:
    assert score_explanation(tutor.model, "M01", GOOD)[0] == "clear"
    assert score_explanation(tutor.model, "M01", BAD)[0] == "tricky"
    assert score_explanation(tutor.model, "M01", "no force")[0] == "needs_more"


def test_report_present() -> None:
    r = json.loads((ROOT / "reports" / "metrics.json").read_text(encoding="utf-8"))["explain_back"]
    assert sum(r["counts"]["holds"].values()) == 12 and sum(r["counts"]["sound"].values()) == 12
    assert r["holding_not_cleared"] >= 0.75


def test_evidence_moves_mastery(tutor) -> None:
    before = tutor.store.mastery("L", "force_motion").mean
    assert svc.check_explanation(tutor, "L", "M01", GOOD)[0] == "clear"
    up = tutor.store.mastery("L", "force_motion").mean
    assert svc.check_explanation(tutor, "L", "M01", BAD)[0] == "tricky"
    down = tutor.store.mastery("L", "force_motion").mean
    assert up > before and down < up
    events = [e for e in tutor.store.timeline("L") if e["kind"] == "explain_back"]
    assert [e["status"] for e in events] == ["clear", "tricky"]


def test_explain_phase_in_flow_and_skip(tutor) -> None:
    engine = LessonEngine(tutor)
    flow = start_demo(engine)
    index = next(i for i, s in enumerate(STEPS) if "explain the idea back" in s.label)
    for step in STEPS[: index + 1]:
        step.action(engine, flow)
    assert flow.phase == "explain" and flow.explain_for == "M01"
    fb = engine.check_explanation(flow, "too short")
    assert fb.status == "needs_more" and flow.phase == "explain"
    engine.skip_explanation(flow)
    assert flow.phase == "question" and flow.explain_for is None
