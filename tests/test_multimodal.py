import json
import xml.etree.ElementTree as ET

import pytest

from relearn.config import ROOT
from relearn.content import load_content
from relearn.learner.store import LearnerStore
from relearn.multimodal.diagrams import diagram_svg, load_visuals
from relearn.multimodal.modality import available, choose_modality
from relearn.multimodal.policy import modality_stats
from relearn.multimodal.simulations import KINDS, simulation_html
from relearn.pipeline import Tutor
from relearn.schemas import LearnerResponse

ALL = sorted(load_content().misconceptions)
BANNED = ["misconception", "confidence", "probability", "strategy"]


@pytest.mark.parametrize("m", ALL)
def test_diagram_is_valid_accessible_svg(m: str) -> None:
    svg = diagram_svg(m)
    root = ET.fromstring(svg)
    ns = "{http://www.w3.org/2000/svg}"
    assert root.attrib["role"] == "img"
    assert root.find(f"{ns}title").text and root.find(f"{ns}desc").text
    assert not any(b in svg.lower() for b in BANNED)


def test_every_misconception_has_a_simulation_and_all_kinds_are_used() -> None:
    kinds = {load_visuals()[m]["simulation"]["kind"] for m in ALL}
    assert kinds == KINDS
    for m in ALL:
        page = simulation_html(m)
        assert page.startswith("<!doctype html>") and 'aria-live="polite"' in page and "KINDS[" in page
        assert "autoplay" not in page


def test_choose_modality_prefers_untried_then_best() -> None:
    m = "M01"
    assert set(available(m)) == {"text", "diagram", "simulation"}
    first, _ = choose_modality(m, {}, ["text"], "s")
    assert first in ("diagram", "simulation")
    picks = [
        choose_modality(m, {"text": (1, 40), "diagram": (1, 40), "simulation": (40, 1)}, [], f"s{i}")[0]
        for i in range(30)
    ]
    assert picks.count("simulation") >= 27


def test_pipeline_logs_modality_and_learns_outcome(tmp_path) -> None:
    from relearn.models.loader import get_active_model

    tutor = Tutor(LearnerStore(tmp_path / "mm.db"), get_active_model().model)
    r = LearnerResponse(question_id="q", answer="2.7 N", working="The force from the hit keeps it moving forward.")
    first = tutor.intervene("L", "M01", r)
    second = tutor.intervene("L", "M01", r)
    assert first.modality != second.modality
    logged = [e for e in tutor.store.timeline("L") if e["kind"] == "intervention"]
    assert [e["modality"] for e in logged] == [first.modality, second.modality]
    assert "modality_draws" in logged[-1]
    items = tutor.plan("L", "M01")
    tutor.submit_assessment("L", "M01", items, {i.item_id: i.correct_answer for i in items})
    stats = modality_stats(tutor.store, "M01")
    assert stats[second.modality]["success"] == 1
    assert sum(v["delivered"] for v in stats.values()) == 2


def test_simulated_comparison_reported() -> None:
    m = json.loads((ROOT / "reports" / "metrics.json").read_text(encoding="utf-8"))["modality_simulation"]
    res = m["results"]
    assert m["assumptions"]["label"].startswith("Simulated")
    assert set(res) == {"text_only", "fixed_rotation", "random", "adaptive"}
    assert res["adaptive"]["first_try_resolution"]["mean"] > res["text_only"]["first_try_resolution"]["mean"]


def test_student_hint_carries_visual(tmp_path) -> None:
    from relearn.learning.flow import LessonEngine
    from relearn.learning.items import practice_item
    from relearn.models.loader import get_active_model

    engine = LessonEngine(Tutor(LearnerStore(tmp_path / "h.db"), get_active_model().model))
    t = next(t for t in load_content().templates if t.template_id == "m09_kicked_ball_02")
    flow = engine.start("S", "force_motion", item=practice_item(t, {"m": 0.45, "v": 6}))
    modalities = set()
    for _ in range(3):
        if flow.phase == "feedback":
            engine.try_again(flow)
        engine.check(flow, "2.7 N", "The force from the hit keeps it moving forward.")
        while flow.phase == "quick_check":
            probe = flow.pending["choice"].probe
            engine.answer_quick_check(flow, probe.expected_answer_by_label.get("M01", probe.options[0]))
        modalities.add(flow.feedback.modality)
        assert flow.feedback.visual_for is not None
    assert modalities & {"diagram", "simulation"}
