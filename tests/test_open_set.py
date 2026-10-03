import json

from relearn.config import ROOT
from relearn.content import load_content
from relearn.data.generator import make_question
from relearn.diagnosis.diagnoser import diagnose
from relearn.diagnosis.routing import open_set_threshold
from relearn.learner.store import LearnerStore
from relearn.models.loader import get_active_model
from relearn.pipeline import Tutor
from relearn.schemas import LearnerResponse


def test_open_set_report() -> None:
    o = json.loads((ROOT / "reports" / "metrics.json").read_text(encoding="utf-8"))["open_set"]
    assert set(o["per_misconception"]) == set(load_content().misconceptions)
    assert o["selected_score"] in o["scores"]
    chosen = o["scores"][o["selected_score"]]
    assert 0.5 <= chosen["test_auroc"] <= 1.0 and 0 <= chosen["test_false_flag_rate"] <= 1
    assert chosen["val_auroc"] == max(s["val_auroc"] for s in o["scores"].values())
    assert abs(open_set_threshold() - chosen["threshold"]) < 1e-3


def test_novelty_only_flags_wrong_answers() -> None:
    model = get_active_model().model
    t = next(t for t in load_content().templates if t.template_id == "m01_puck_ice_01")
    q = make_question(t, {"m": 0.5, "v": 8})
    right = diagnose(
        q, LearnerResponse(question_id="q", answer="0 N", working="no net force at constant velocity"), model
    )
    assert 0.0 <= right.novelty <= 1.0 and not right.unfamiliar
    known = diagnose(
        q, LearnerResponse(question_id="q", answer="4.0 N forward", working="it needs a force to keep moving"), model
    )
    assert known.novelty < 0.2 and not known.unfamiliar


def test_review_queue_collects_flagged_attempts(tmp_path, monkeypatch) -> None:
    tutor = Tutor(LearnerStore(tmp_path / "q.db"), get_active_model().model)
    t = next(t for t in load_content().templates if t.template_id == "m01_puck_ice_01")
    q = make_question(t, {"m": 0.5, "v": 8})
    monkeypatch.setattr("relearn.diagnosis.diagnoser.open_set_threshold", lambda: 0.0)
    tutor.submit("L", q, LearnerResponse(question_id=q.question_id, answer="4.0 N forward", working="magnets push it"))
    queue = tutor.store.review_queue()
    assert queue and queue[0]["learner"] == "L" and queue[0]["answer"] == "4.0 N forward"
