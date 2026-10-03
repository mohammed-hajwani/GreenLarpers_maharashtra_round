import xml.etree.ElementTree as ET

from relearn import services as svc
from relearn.content import load_content
from relearn.learner.state import new_record, on_diagnosis
from relearn.learner.store import LearnerStore
from relearn.multimodal.maps import STATUS, concept_map_svg
from relearn.pipeline import Tutor

BANNED = ["misconception", "confidence", "probability", "strategy"]


def test_concept_map_reflects_backend_status(tmp_path) -> None:
    tutor = Tutor(LearnerStore(tmp_path / "m.db"))
    svg = svc.concept_map(tutor, "L")
    ET.fromstring(f"<root>{svg}</root>")
    assert svg.count(f"{STATUS['not_started'][1]} {STATUS['not_started'][2]}") == 2 * len(load_content().concepts)
    tutor.store.put(on_diagnosis(new_record("L", "M01"), 0.9))
    svg = svc.concept_map(tutor, "L")
    assert "Force vs Motion: In progress" in svg
    assert not any(b in svg.lower() for b in BANNED)


def test_concept_map_labels_every_status() -> None:
    svg = concept_map_svg({"force_motion": "mastered", "energy": "review"})
    assert "✓ Mastered" in svg and "↺ Come back to this" in svg


def test_class_map_counts(tmp_path) -> None:
    tutor = Tutor(LearnerStore(tmp_path / "c.db"))
    for learner in ("A", "B"):
        tutor.store.put(on_diagnosis(new_record(learner, "M01"), 0.9))
    resolved = new_record("C", "M01").model_copy(update={"state": "resolved"})
    tutor.store.put(resolved)
    data = svc.class_map_data(tutor)
    assert data["M01"]["held"] == 3 and data["M01"]["resolved"] == 1
    ET.fromstring(svc.class_map(tutor))
