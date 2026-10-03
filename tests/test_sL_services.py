import ast
from pathlib import Path

from relearn import services as svc
from relearn.config import ROOT
from relearn.content import load_content
from relearn.data.generator import make_question
from relearn.learner.store import LearnerStore
from relearn.pipeline import Tutor
from relearn.schemas import LearnerResponse

FORBIDDEN_IMPORTS = {
    "relearn.models",
    "relearn.diagnosis",
    "relearn.learner.store",
    "relearn.analytics",
    "relearn.pipeline",
}


def _question():
    t = next(t for t in load_content().templates if t.template_id == "m09_kicked_ball_02")
    return make_question(t, {"m": 0.45, "v": 6})


def test_service_flow(tmp_path) -> None:
    tutor = Tutor(LearnerStore(tmp_path / "l.db"), svc.active_model().model)
    q = _question()
    r = LearnerResponse(
        question_id=q.question_id, answer="2.7 N", working="The force from the hit keeps it moving forward."
    )
    pred = svc.predict(q, r)
    assert pred.top_labels and pred.model_name == svc.active_model().model.name
    assert svc.explain_prediction(q, r, pred.top_labels[0][0])["methods"]
    d = svc.diagnose(tutor, "L", q, r)
    initial, steps, used = d, [], set()
    while (choice := svc.next_probe(tutor, d, used)) is not None:
        used.add(choice.probe.probe_id)
        d, step = svc.answer_probe(
            tutor, "L", d, choice, choice.probe.expected_answer_by_label.get("M01", choice.probe.options[0])
        )
        steps.append(step)
    trace = svc.finalize(tutor, "L", q, r, initial, d, steps)
    assert svc.trace(tutor, trace["id"]) == trace
    iv = svc.intervention(tutor, "L", "M01", r)
    assert iv.sources
    items = svc.plan_assessment(tutor, "L", "M01")
    result, record = svc.submit_assessment(tutor, "L", "M01", items, {i.item_id: i.correct_answer for i in items})
    assert result.trap_passed and record.state.value == "intervened"
    assert svc.pending_retest(tutor, "L", "M01") == 3
    assert "force_motion" in svc.mastery(tutor, "L")
    assert svc.progress(tutor, "L", "force_motion")["label"].startswith("Estimate based on simulated learners")
    assert svc.next_question(tutor, "L")[1].headline
    assert not svc.dashboard(tutor, "L")["empty"]
    assert svc.evaluate()["available"]
    assert svc.profile(tutor, "L") and svc.timeline(tutor, "L")
    svc.reset(tutor, "L")
    assert svc.timeline(tutor, "L") == []


def test_ui_imports_only_services() -> None:
    for path in (ROOT / "src" / "relearn" / "app").glob("*.py"):
        tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert (
                    not any(node.module.startswith(f) for f in FORBIDDEN_IMPORTS)
                    or node.module == "relearn.pipeline"
                    and all(a.name == "Tutor" for a in node.names)
                ), (path.name, node.module)
