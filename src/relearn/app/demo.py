import json
from pathlib import Path

from relearn.config import ROOT
from relearn.content import load_content
from relearn.data.generator import make_question
from relearn.pipeline import Tutor
from relearn.schemas import AssessmentItem, LearnerResponse

SCRIPT_PATH = ROOT / "content" / "demo_script.json"


def load_script(path: Path = SCRIPT_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _question(template_id: str, params: dict):
    t = next(t for t in load_content().templates if t.template_id == template_id)
    return make_question(t, params)


def _wrong(item: AssessmentItem) -> str:
    if item.trap_answer_maps_to:
        return next(iter(item.trap_answer_maps_to))
    return next(o for o in item.options if o != item.correct_answer)


def _item_rows(items: list[AssessmentItem], answers: dict, correct: dict) -> list[dict]:
    return [
        {"kind": i.kind, "stem": i.stem, "answer": answers[i.item_id], "correct": correct[i.item_id]}
        for i in items
    ]


def _round(tutor: Tutor, learner: str, m: str, correct_kinds: list[str] | None) -> dict:
    items = tutor.plan(learner, m)
    answers = {}
    remaining = list(correct_kinds) if correct_kinds is not None else None
    for i in items:
        ok = remaining is None or i.kind in remaining
        if remaining is not None and ok:
            remaining.remove(i.kind)
        answers[i.item_id] = i.correct_answer if ok else _wrong(i)
    result, record = tutor.submit_assessment(learner, m, items, answers)
    return {
        "items": _item_rows(items, answers, result.item_correct),
        "transfer": f"{result.transfer_correct}/{result.transfer_total}",
        "trap_passed": result.trap_passed,
        "state": record.state.value,
        "pending_retest_in": tutor.pending_retest(learner, m),
    }


def run_demo(tutor: Tutor, script: dict | None = None) -> list[dict]:
    script = script or load_script()
    learner = script["learner_id"]
    tutor.store.reset(learner)
    steps: list[dict] = []
    p = script["practice"]
    q = _question(p["template_id"], p["params"])
    response = LearnerResponse(question_id=q.question_id, answer=p["answer"], working=p["working"])
    d = tutor.submit(learner, q, response)
    steps.append(
        {
            "kind": "diagnosis",
            "title": "1. Learner submits a wrong answer",
            "data": {
                "stem": q.stem,
                "answer": response.answer,
                "working": response.working,
                **d.model_dump(),
            },
        }
    )
    used: set[str] = set()
    while (choice := tutor.next_probe(d, used)) is not None:
        probe = choice.probe
        answer = probe.expected_answer_by_label.get(script["held_misconception"], probe.options[0])
        used.add(probe.probe_id)
        before = d.top_labels
        d, step = tutor.answer_probe(learner, d, choice, answer)
        steps.append(
            {
                "kind": "probe",
                "title": "2. Top labels are close, so a probe separates them",
                "data": {
                    "stem": probe.stem,
                    "options": probe.options,
                    "answer": answer,
                    "before": before,
                    **d.model_dump(),
                },
            }
        )
    tutor.confirm(learner, d)
    m = d.top_labels[0][0]
    iv = tutor.intervene(learner, m, response)
    steps.append({"kind": "intervention", "title": "3. Targeted intervention", "data": iv.model_dump()})
    r1 = _round(tutor, learner, m, script["round_1_correct_kinds"])
    steps.append(
        {"kind": "assessment", "title": "4. Reassessment: passes follow-ups, fails the trap", "data": r1}
    )
    iv2 = tutor.intervene(learner, m, response)
    steps.append(
        {"kind": "intervention", "title": "5. Escalation to a second strategy", "data": iv2.model_dump()}
    )
    r2 = _round(tutor, learner, m, None if script["round_2_all_correct"] else [])
    steps.append({"kind": "assessment", "title": "6. Reassessment: transfer and trap passed", "data": r2})
    fillers = []
    for f in script["filler_practice"]:
        fq = _question(f["template_id"], f["params"])
        fd = tutor.submit(learner, fq, LearnerResponse(question_id=fq.question_id, answer=fq.correct_answer))
        fillers.append({"stem": fq.stem, "answer": fq.correct_answer, "correct": fd.is_correct})
    steps.append(
        {"kind": "practice", "title": "7. Other practice in between (spacing)", "data": {"rows": fillers}}
    )
    due = tutor.due_retests(learner)
    _, item = next(x for x in due if x[0] == m)
    answer = item.correct_answer if script["retest_correct"] else _wrong(item)
    result, record = tutor.submit_retest(learner, item, answer)
    steps.append(
        {
            "kind": "retest",
            "title": "8. Delayed retest",
            "data": {
                "stem": item.stem,
                "answer": answer,
                "correct": result.retest_passed,
                "state": record.state.value,
            },
        }
    )
    steps.append(
        {
            "kind": "profile",
            "title": "9. Learner profile",
            "data": {"rows": tutor.profile(learner), "timeline": tutor.store.timeline(learner)},
        }
    )
    return steps
