import json
from pathlib import Path

from relearn import services as svc
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


def _round(tutor: Tutor, learner: str, m: str, correct_kinds: list[str] | None) -> dict:
    items = svc.plan_assessment(tutor, learner, m)
    answers = {}
    remaining = list(correct_kinds) if correct_kinds is not None else None
    for i in items:
        ok = remaining is None or i.kind in remaining
        if remaining is not None and ok:
            remaining.remove(i.kind)
        answers[i.item_id] = i.correct_answer if ok else _wrong(i)
    result, record = svc.submit_assessment(tutor, learner, m, items, answers)
    trace = tutor.last_trace
    return {
        "items": [
            {"kind": i.kind, "stem": i.stem, "answer": answers[i.item_id], "correct": result.item_correct[i.item_id]}
            for i in items
        ],
        "transfer": f"{result.transfer_correct}/{result.transfer_total}",
        "trap_passed": result.trap_passed,
        "state": record.state.value,
        "pending_retest_in": svc.pending_retest(tutor, learner, m),
        "mastery_before": trace["mastery_updates"][0]["before"],
        "mastery_after": trace["mastery_updates"][-1]["after"],
        "trace": trace,
    }


def _probe_phase(tutor: Tutor, learner: str, d, held: str) -> tuple:
    used: set[str] = set()
    probe_steps, cards = [], []
    while (choice := svc.next_probe(tutor, d, used)) is not None:
        probe = choice.probe
        answer = probe.expected_answer_by_label.get(held, probe.options[0])
        used.add(probe.probe_id)
        before = d.top_labels
        d, step = svc.answer_probe(tutor, learner, d, choice, answer)
        probe_steps.append(step)
        cards.append(
            {
                "kind": "probe",
                "title": "2. Diagnostic probe chosen by expected information gain",
                "data": {
                    "stem": probe.stem,
                    "options": probe.options,
                    "answer": answer,
                    "before": before,
                    "expected_gain": step.expected_gain,
                    "runners_up": step.runners_up,
                    "entropy_before": step.entropy_before,
                    "entropy_after": step.entropy_after,
                    **d.model_dump(),
                },
            }
        )
    return d, probe_steps, cards


def _spacing(tutor: Tutor, learner: str, concepts: list[str]) -> list[dict]:
    rows = []
    for concept in concepts:
        q, decision = svc.next_question(tutor, learner, concept)
        r = LearnerResponse(question_id=q.question_id, answer=q.correct_answer)
        d = svc.diagnose(tutor, learner, q, r)
        trace = svc.finalize(tutor, learner, q, r, d, d, [])
        rows.append(
            {
                "why": decision.headline,
                "difficulty": decision.band,
                "stem": q.stem,
                "answer": q.correct_answer,
                "correct": d.is_correct,
                "mastery_after": trace["mastery"]["after"],
            }
        )
    return rows


def run_demo(tutor: Tutor, script: dict | None = None) -> list[dict]:
    script = script or load_script()
    learner = script["learner_id"]
    svc.reset(tutor, learner)
    steps: list[dict] = []
    p = script["practice"]
    q = _question(p["template_id"], p["params"])
    response = LearnerResponse(question_id=q.question_id, answer=p["answer"], working=p["working"])
    initial = svc.diagnose(tutor, learner, q, response)
    steps.append(
        {
            "kind": "diagnosis",
            "title": "1. Learner submits a wrong answer",
            "data": {"stem": q.stem, "answer": response.answer, "working": response.working, **initial.model_dump()},
        }
    )
    d, probe_steps, cards = _probe_phase(tutor, learner, initial, script["held_misconception"])
    steps.extend(cards)
    trace = svc.finalize(tutor, learner, q, response, initial, d, probe_steps)
    steps.append({"kind": "trace", "title": "3. AI decision trace for this answer", "data": trace})
    m = d.misconception
    iv = svc.intervention(tutor, learner, m, response)
    steps.append({"kind": "intervention", "title": "4. Targeted intervention", "data": iv.model_dump()})
    r1 = _round(tutor, learner, m, script["round_1_correct_kinds"])
    steps.append({"kind": "assessment", "title": "5. Reassessment: passes follow-ups, fails the trap", "data": r1})
    iv2 = svc.intervention(tutor, learner, m, response)
    steps.append({"kind": "intervention", "title": "6. Escalation to a second strategy", "data": iv2.model_dump()})
    r2 = _round(tutor, learner, m, None if script["round_2_all_correct"] else [])
    steps.append({"kind": "assessment", "title": "7. Reassessment: transfer and trap passed", "data": r2})
    rows = _spacing(tutor, learner, script["spacing_concepts"])
    steps.append({"kind": "practice", "title": "8. Adaptive practice in between (spacing)", "data": {"rows": rows}})
    _, item = next(x for x in svc.due_retests(tutor, learner) if x[0] == m)
    answer = item.correct_answer if script["retest_correct"] else _wrong(item)
    result, record = svc.submit_retest(tutor, learner, item, answer)
    retest_trace = tutor.last_trace
    steps.append(
        {
            "kind": "retest",
            "title": "9. Delayed retest",
            "data": {
                "stem": item.stem,
                "answer": answer,
                "correct": result.retest_passed,
                "state": record.state.value,
                "mastery_before": retest_trace["mastery_updates"][0]["before"],
                "mastery_after": retest_trace["mastery_updates"][-1]["after"],
            },
        }
    )
    _, decision = svc.next_question(tutor, learner)
    steps.append(
        {
            "kind": "next",
            "title": "10. Adaptive next question",
            "data": {"headline": decision.headline, "band": decision.band, "reasons": decision.reasons},
        }
    )
    steps.append(
        {
            "kind": "profile",
            "title": "11. Learner profile and dashboard",
            "data": {
                "rows": svc.profile(tutor, learner),
                "timeline": svc.timeline(tutor, learner),
                "dashboard": svc.dashboard(tutor, learner),
            },
        }
    )
    return steps
