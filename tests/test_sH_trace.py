import pytest
from streamlit.testing.v1 import AppTest

from relearn.app.trace_view import assessment_rows, pct, practice_rows
from relearn.config import ROOT
from relearn.content import load_content
from relearn.data.generator import make_question
from relearn.diagnosis.explain import explain
from relearn.learner.store import LearnerStore
from relearn.models.loader import get_active_model
from relearn.models.registry import BASELINE, load_model
from relearn.pipeline import Tutor
from relearn.schemas import LearnerResponse

WORKING = "The force from the hit keeps it moving forward."


def _question():
    t = next(t for t in load_content().templates if t.template_id == "m09_kicked_ball_02")
    return make_question(t, {"m": 0.45, "v": 6})


def _flow(tutor: Tutor) -> tuple[dict, list[dict]]:
    q = _question()
    r = LearnerResponse(question_id=q.question_id, answer="2.7 N", working=WORKING)
    initial = tutor.submit("L", q, r)
    d, steps, used = initial, [], set()
    while (choice := tutor.next_probe(d, used)) is not None:
        used.add(choice.probe.probe_id)
        d, step = tutor.answer_probe(
            "L", d, choice, choice.probe.expected_answer_by_label.get("M01", choice.probe.options[0])
        )
        steps.append(step)
    trace = tutor.finalize_interaction("L", q, r, initial, d, steps)
    tutor.intervene("L", d.top_labels[0][0], r)
    items = tutor.plan("L", d.top_labels[0][0])
    tutor.submit_assessment("L", d.top_labels[0][0], items, {i.item_id: i.correct_answer for i in items})
    return trace, [initial, d, steps]


def test_full_flow_writes_traces(tmp_path) -> None:
    tutor = Tutor(LearnerStore(tmp_path / "h.db"), get_active_model().model)
    trace, (initial, final, steps) = _flow(tutor)
    stored = tutor.store.traces("L")
    assert [t["kind"] for t in stored] == ["practice", "assessment"]
    assert stored[0] == trace
    assert trace["initial"]["confidence"] == pytest.approx(initial.confidence)
    assert trace["initial"]["route"] == initial.route == "probe"
    assert trace["final"]["confidence"] == pytest.approx(final.confidence)
    assert trace["final"]["predicted"] == "M01"
    assert len(trace["probes"]) == len(steps) >= 1
    assert trace["probes"][0]["entropy_before"] == pytest.approx(initial.entropy)
    assert trace["mastery"]["after"] == pytest.approx(tutor.store.mastery_history("L")[-1 - 4]["after"])
    assert trace["model_name"] == tutor.model.name
    assert trace["next_difficulty"]["mastery"] == pytest.approx(trace["mastery"]["after"])
    assert len(trace["input_hash"]) == 16
    assert stored[1]["mastery_updates"]


def test_displayed_values_match_stored(tmp_path) -> None:
    tutor = Tutor(LearnerStore(tmp_path / "h2.db"), get_active_model().model)
    trace, _ = _flow(tutor)
    record = tutor.store.trace(trace["id"])
    rows = dict(practice_rows(record))
    assert pct(record["final"]["confidence"]) in rows["Final prediction"]
    assert pct(record["initial"]["confidence"]) in rows["Initial prediction"]
    assert f"{record['probes'][0]['information_gain']:.3f} bits" == rows["Probe 1 information gain"]
    assert pct(record["mastery"]["before"]) in rows["Mastery"] and pct(record["mastery"]["after"]) in rows["Mastery"]
    assert rows["Next difficulty reason"] == record["next_difficulty"]["headline"]
    a_rows = dict(assessment_rows(tutor.store.traces("L")[-1]))
    assert a_rows["Transfer"] == tutor.store.traces("L")[-1]["transfer"]


def test_explanations_come_from_models() -> None:
    q = _question()
    r = LearnerResponse(question_id=q.question_id, answer="2.7 N", working=WORKING)
    base = explain(load_model(BASELINE), q, r, "M09")
    assert base["methods"] == ["tfidf_coefficients"] and base["influential_features"]
    active = get_active_model().model
    exp = explain(active, q, r, "M09")
    if active.kind == "v1_embedding":
        assert {"nearest_training_examples", "token_occlusion"} <= set(exp["methods"])
        assert all(-1 <= e["cosine"] <= 1 for e in exp["similar_examples"])
        assert {o["word"] for o in exp["occlusion"]} <= set(WORKING.split())


def test_app_renders_stored_trace(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("RELEARN_DB", str(tmp_path / "app.db"))
    q = _question()
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    at.run()
    at.session_state["question"] = q
    at.session_state["phase"] = "answer"
    at.run()
    at.text_input[0].input("2.7 N")
    at.text_area[-1].input(WORKING)
    next(b for b in at.button if b.label == "Submit").click()
    at.run()
    while at.session_state["phase"] == "probe":
        choice = at.session_state["probe"]
        next(r for r in at.radio if r.key == "probe_ans").set_value(
            choice.probe.expected_answer_by_label.get("M01", choice.probe.options[0])
        )
        next(b for b in at.button if b.label == "Answer probe").click()
        at.run()
    assert not at.exception
    tutor = at.session_state["trace_id"]
    from relearn.app.streamlit_app import get_tutor

    record = get_tutor().store.trace(tutor)
    shown = {row["field"]: row["value"] for row in at.table[-1].value.to_dict("records")}
    assert shown == dict(practice_rows(record))
