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
    t = next(t for t in load_content().templates if t.template_id == "m01_car_cruise_02")
    q = make_question(t, {"v": 80})
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
    at.run()
    landing = banned_hits(element_text(at))
    if "question" in at.session_state and "phase" in at.session_state:
        at.session_state["question"] = q
        at.session_state["phase"] = "answer"
        at.run()
    radios = [r for r in at.radio if r.label in ("Your answer",)]
    after_wrong = {}
    if radios:
        radios[0].set_value(q.options[0])
        at.text_area[-1].input("The engine force must be bigger than friction or the car would stop.")
        next(b for b in at.button if b.label in ("Submit", "Check answer")).click()
        at.run()
        after_wrong = banned_hits(element_text(at))
    return {"landing": landing, "after_wrong_answer": after_wrong, "exceptions": len(at.exception)}


def main() -> None:
    label = sys.argv[1] if len(sys.argv) > 1 else "run"
    with tempfile.TemporaryDirectory() as tmp:
        tutor = Tutor(LearnerStore(Path(tmp) / "r.db"))
        result = {
            "repeats": repeats_in_session(tutor, "R"),
            "screening_flags": screening_cases(),
            "student_view_banned_strings": student_view_hits(),
        }
        tutor.store.conn.close()
    out = ROOT / "docs" / "test_runs" / f"{label}_readings.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
