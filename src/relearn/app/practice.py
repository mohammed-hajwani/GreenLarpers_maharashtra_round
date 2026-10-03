import streamlit as st

from relearn import services as svc
from relearn.app.trace_view import render_assessment_trace, render_practice_trace
from relearn.app.views import (
    label_name,
    render_assessment,
    render_diagnosis,
    render_intervention,
    status_line,
)
from relearn.content import load_content
from relearn.pipeline import Tutor
from relearn.schemas import LearnerResponse, Question, QuestionType

KEYS = [
    "question",
    "phase",
    "diagnosis",
    "response",
    "probes_used",
    "probe",
    "intervention",
    "assess_items",
    "last_result",
    "round",
    "decision",
    "probe_steps",
    "initial_diagnosis",
    "trace_id",
    "assessment_trace_id",
]


def reset_flow() -> None:
    for k in KEYS:
        st.session_state.pop(k, None)


def _topic_picker(tutor: Tutor, learner: str) -> None:
    content = load_content()
    options = ["auto"] + list(content.concepts)
    cols = st.columns([3, 1])
    concept = cols[0].selectbox(
        "Concept",
        options,
        format_func=lambda c: "Adaptive: let the system choose" if c == "auto" else content.concepts[c].name,
    )
    if cols[1].button("Next question", width="stretch") or "question" not in st.session_state:
        reset_flow()
        question, decision = svc.next_question(tutor, learner, None if concept == "auto" else concept)
        st.session_state.question = question
        st.session_state.decision = decision
        st.session_state.phase = "answer"
    decision = st.session_state.get("decision")
    if decision is not None and st.session_state.question.template_id == decision.template_id:
        with st.container(border=True):
            st.markdown(f"**{decision.headline}**")
            st.caption(f"Difficulty: **{decision.band}** · " + "; ".join(decision.reasons))


def _custom_question() -> None:
    with st.expander("Ask your own question (free text)"):
        stem = st.text_area("Question stem", key="custom_stem")
        if st.button("Use this question") and stem.strip():
            reset_flow()
            st.session_state.question = Question(
                question_id="custom",
                template_id="custom",
                question_type=QuestionType.explanation,
                stem=stem.strip(),
                correct_answer="",
            )
            st.session_state.phase = "answer"


def _answer_form(tutor: Tutor, learner: str) -> None:
    q: Question = st.session_state.question
    st.markdown(f"### {q.stem}")
    with st.form("answer_form"):
        if q.question_type == QuestionType.mcq:
            answer = st.radio("Your answer", q.options, index=None)
        else:
            answer = st.text_input("Your answer")
        working = st.text_area("Explain your reasoning", height=90)
        if st.form_submit_button("Submit", type="primary") and answer:
            response = LearnerResponse(question_id=q.question_id, answer=answer, working=working)
            st.session_state.response = response
            st.session_state.diagnosis = svc.diagnose(tutor, learner, q, response)
            st.session_state.initial_diagnosis = st.session_state.diagnosis
            st.session_state.probe_steps = []
            st.session_state.probes_used = set()
            _advance_probe(tutor, learner)
            st.rerun()


def _advance_probe(tutor: Tutor, learner: str) -> None:
    choice = svc.next_probe(tutor, st.session_state.diagnosis, st.session_state.probes_used)
    st.session_state.probe = choice
    if choice is None:
        trace = svc.finalize(
            tutor,
            learner,
            st.session_state.question,
            st.session_state.response,
            st.session_state.initial_diagnosis,
            st.session_state.diagnosis,
            st.session_state.probe_steps,
        )
        st.session_state.trace_id = trace["id"]
        st.session_state.phase = "diagnosed"
    else:
        st.session_state.phase = "probe"


def _probe_form(tutor: Tutor, learner: str) -> None:
    choice = st.session_state.probe
    probe = choice.probe
    st.info("Your answer fits two closely related ideas. One quick question to tell them apart:")
    with st.form("probe_form"):
        st.markdown(f"**{probe.stem}**")
        answer = st.radio("Choose", probe.options, index=None, label_visibility="collapsed", key="probe_ans")
        if st.form_submit_button("Answer probe") and answer:
            st.session_state.probes_used.add(probe.probe_id)
            st.session_state.diagnosis, step = svc.answer_probe(
                tutor, learner, st.session_state.diagnosis, choice, answer
            )
            st.session_state.setdefault("probe_steps", []).append(step)
            _advance_probe(tutor, learner)
            st.rerun()


def _assessment_form(tutor: Tutor, learner: str, m: str) -> None:
    items = st.session_state.assess_items
    with st.form(f"assess_{st.session_state.get('round', 0)}"):
        answers = {}
        for i in items:
            answers[i.item_id] = st.radio(i.stem, i.options, index=None, key=f"a_{i.item_id}_{st.session_state.round}")
        if st.form_submit_button("Submit answers", type="primary"):
            result, record = svc.submit_assessment(tutor, learner, m, items, {k: v or "" for k, v in answers.items()})
            rows = [
                {
                    "kind": i.kind,
                    "stem": i.stem,
                    "answer": answers[i.item_id] or "",
                    "correct": result.item_correct[i.item_id],
                }
                for i in items
            ]
            st.session_state.last_result = {
                "items": rows,
                "transfer": f"{result.transfer_correct}/{result.transfer_total}",
                "trap_passed": result.trap_passed,
                "state": record.state.value,
                "pending_retest_in": svc.pending_retest(tutor, learner, m),
            }
            st.session_state.assessment_trace_id = tutor.last_trace["id"]
            st.session_state.phase = "assessed"
            st.rerun()


def _retest_banner(tutor: Tutor, learner: str) -> None:
    for m, item in svc.due_retests(tutor, learner):
        with st.container(border=True):
            st.markdown(f"**Delayed retest** for {label_name(m)}")
            choice = st.radio(item.stem, item.options, index=None, key=f"retest_{item.item_id}")
            if st.button("Submit retest", key=f"rt_{item.item_id}") and choice:
                _, record = svc.submit_retest(tutor, learner, item, choice)
                st.session_state.retest_msg = (m, record.state.value)
                st.rerun()
    if msg := st.session_state.pop("retest_msg", None):
        status_line(msg[1], None, None)


def render_practice(tutor: Tutor, learner: str) -> None:
    _retest_banner(tutor, learner)
    _topic_picker(tutor, learner)
    _custom_question()
    phase = st.session_state.phase
    if phase == "answer":
        _answer_form(tutor, learner)
        return
    d = st.session_state.diagnosis
    r = st.session_state.response
    st.markdown(f"### {st.session_state.question.stem}")
    render_diagnosis({**d.model_dump(), "stem": "", "answer": r.answer, "working": r.working})
    if phase == "probe":
        _probe_form(tutor, learner)
        return
    if st.session_state.get("trace_id"):
        render_practice_trace(svc.trace(tutor, st.session_state.trace_id))
    if d.is_correct:
        return
    m = d.top_labels[0][0]
    if phase == "diagnosed" and st.button("Help me with this", type="primary"):
        st.session_state.intervention = svc.intervention(tutor, learner, m, r)
        st.session_state.phase = "intervened"
        st.rerun()
    if phase in ("intervened", "assessing", "assessed"):
        iv = st.session_state.intervention
        if iv is None:
            st.warning("All strategies tried for this misconception. Flagged for a human tutor.")
            return
        render_intervention(iv.model_dump())
    if phase == "intervened" and st.button("Check my understanding", type="primary"):
        st.session_state.assess_items = svc.plan_assessment(tutor, learner, m)
        st.session_state.round = st.session_state.get("round", 0) + 1
        st.session_state.phase = "assessing"
        st.rerun()
    if phase == "assessing":
        _assessment_form(tutor, learner, m)
    if phase == "assessed":
        result = st.session_state.last_result
        render_assessment(result)
        if st.session_state.get("assessment_trace_id"):
            render_assessment_trace(svc.trace(tutor, st.session_state.assessment_trace_id))
        if result["state"] in ("active", "relapsed") and st.button("Try another explanation", type="primary"):
            st.session_state.intervention = svc.intervention(tutor, learner, m, r)
            st.session_state.phase = "intervened"
            st.rerun()
