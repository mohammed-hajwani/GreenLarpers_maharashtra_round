import ast

from conftest import insights_app
from streamlit.testing.v1 import AppTest

from relearn.config import ROOT
from relearn.content import load_content
from relearn.data.generator import make_question
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
STUDENT_DIR = ROOT / "src" / "relearn" / "app" / "student"
KINDS = (
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
    "form_submit_button",
)


def page_text(at: AppTest) -> str:
    parts = []
    for kind in KINDS:
        for el in getattr(at, kind, []):
            for attr in ("value", "label", "body", "options"):
                v = getattr(el, attr, None)
                if v is not None and not callable(v):
                    parts.append(str(v))
    return "\n".join(parts)


def assert_clean(at: AppTest) -> None:
    text = page_text(at).lower()
    hits = [b for b in BANNED if b.lower() in text]
    assert not hits, hits


def test_student_modules_never_import_insights() -> None:
    for path in STUDENT_DIR.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "insights" not in node.module, (path.name, node.module)
                assert not node.module.startswith("relearn.diagnosis.explain"), path.name
            if isinstance(node, ast.Import):
                assert all("insights" not in a.name for a in node.names), path.name


def test_student_landing_is_clean(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("RELEARN_DB", str(tmp_path / "s.db"))
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
    at.run()
    assert not at.exception
    assert_clean(at)
    assert any("Insights (for judges and teachers)" in m.value for m in at.markdown)


def _seed_learner(learner: str) -> None:
    from relearn.app.streamlit_app import get_tutor

    tutor = get_tutor()
    t = next(t for t in load_content().templates if t.template_id == "m09_kicked_ball_02")
    q = make_question(t, {"m": 0.45, "v": 6})
    r = LearnerResponse(
        question_id=q.question_id, answer="2.7 N", working="The force from the hit keeps it moving forward."
    )
    d = tutor.submit(learner, q, r)
    tutor.finalize_interaction(learner, q, r, d, d, [])
    tutor.intervene(learner, d.misconception or "M09", r)


def test_insights_shows_every_moved_element() -> None:
    learner = "insights-check"
    first = insights_app()
    _seed_learner(learner)
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
    at.query_params["view"] = "insights"
    at.query_params["learner"] = learner
    at.run()
    assert not at.exception and not first.exception
    expanders = [e.label for e in at.expander]
    assert "Why did the AI make this prediction?" in expanders
    assert "AI Decision Trace" in expanders
    assert any("strategy and sources" in s.value for s in at.subheader)
    table = at.dataframe[-1].value
    assert {"strategy", "sources", "mode"} <= set(table.columns) and table["sources"].str.len().max() > 0
    at.sidebar.radio[0].set_value("Model Evaluation")
    at.run()
    assert at.dataframe and not at.exception
    at.sidebar.radio[0].set_value("Dashboard")
    at.run()
    assert at.metric and not at.exception
