import json
import sys
import tempfile
from pathlib import Path

from streamlit.testing.v1 import AppTest

from relearn.config import ROOT
from relearn.content import load_content
from relearn.data.generator import make_question
from relearn.diagnosis.screening import screen_response
from relearn.learner.store import LearnerStore
from relearn.pipeline import Tutor
from relearn.schemas import LearnerResponse

BANNED = [
    "Decision Trace",
    "Why the AI",
    "Sources Used",
    "Strategy",
    "Model Evaluation",
    "confidence",
    "probability",
    "misconception",
]


def element_text(at: AppTest) -> str:
    parts = []
    for kind in (
        "markdown",
        "caption",
        "info",
        "warning",
        "error",
        "success",
        "subheader",
        "header",
        "title",
        "expander",
        "button",
        "radio",
        "text_input",
        "text_area",
        "selectbox",
        "table",
        "dataframe",
        "metric",
    ):
        for el in getattr(at, kind, []):
            for attr in ("value", "label", "body"):
                v = getattr(el, attr, None)
                if v is not None and not callable(v):
                    parts.append(str(v))
    return "\n".join(parts)


def banned_hits(text: str) -> dict[str, int]:
    low = text.lower()
    return {b: low.count(b.lower()) for b in BANNED if b.lower() in low}


def repeats_in_session(tutor: Tutor, learner: str, n: int = 10) -> dict:
    stems = [tutor.next_question(learner, "force_motion")[0].stem for _ in range(n)]
    return {"questions_requested": n, "unique_stems": len(set(stems))}


def screening_cases() -> dict:
    t = next(t for t in load_content().templates if t.template_id == "m01_puck_ice_01")
    q = make_question(t, {"m": 0.5, "v": 8})
    cases = {
        "idk": ("idk", ""),
        "blank_reasoning_answer": ("0 N", ""),
        "real": ("4.0 N forward", "a force keeps it going"),
    }
    return {
        k: screen_response(q, LearnerResponse(question_id="q", answer=a, working=w)) is not None
        for k, (a, w) in cases.items()
    }


def student_view_hits() -> dict:
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
    at.run()
    landing = banned_hits(element_text(at))
    at.button(key="start-force_motion").click()
    at.run()
    flow = at.session_state["rl_flow"]
    question = flow.item.question
    if question.question_type.value == "mcq":
        at.radio[0].set_value(next(o for o in question.options if o != question.correct_answer))
    else:
        at.text_input[0].input("100 N forward")
    at.text_area[0].input("a force is needed to keep it moving forward")
    next(b for b in at.button if b.label == "Check answer").click()
    at.run()
    while flow.phase == "quick_check":
        at.radio[0].set_value(flow.pending["choice"].probe.options[0])
        next(b for b in at.button if b.label == "Check answer").click()
        at.run()
    after_wrong = banned_hits(element_text(at))
    at.button(key="nav-reveal").click()
    at.run()
    after_reveal = banned_hits(element_text(at))
    return {
        "landing": landing,
        "after_wrong_answer": after_wrong,
        "after_reveal": after_reveal,
        "feedback_status": flow.feedback.status,
        "exceptions": len(at.exception),
    }


def flow_repeats(tutor: Tutor) -> dict:
    from relearn.learning.flow import LessonEngine

    engine = LessonEngine(tutor)
    flow = engine.start("F", "force_motion")
    ids = [flow.item.question.question_id]
    for _ in range(9):
        engine.try_another(flow)
        ids.append(flow.item.question.question_id)
    content = load_content()
    concepts = {
        content.concept_of(
            content.templates[[t.template_id for t in content.templates].index(i.split("__")[0])].primary
        )
        for i in ids
    }
    return {"questions_requested": 10, "unique_question_ids": len(set(ids)), "concepts": sorted(concepts)}


def main() -> None:
    label = sys.argv[1] if len(sys.argv) > 1 else "run"
    with tempfile.TemporaryDirectory() as tmp:
        tutor = Tutor(LearnerStore(Path(tmp) / "r.db"))
        result = {
            "repeats": repeats_in_session(tutor, "R"),
            "flow_try_another": flow_repeats(tutor),
            "screening_flags": screening_cases(),
            "student_view_banned_strings": student_view_hits(),
        }
        tutor.store.conn.close()
    out = ROOT / "docs" / "test_runs" / f"{label}_readings.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
