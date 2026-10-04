from html import escape

import streamlit as st

from relearn import services as svc
from relearn.app.student.components import (
    answer_feedback,
    concept_card,
    explain_card,
    html,
    inject_theme,
    lesson_header,
    progress_indicator,
    question_card,
)
from relearn.content import load_content
from relearn.learning.flow import LessonEngine, LessonFlow
from relearn.learning.guided import STEPS, start_demo
from relearn.pipeline import Tutor

INSIGHTS_LINK = (
    '<p class="rl-footer">Prototype for learning introductory mechanics · '
    '<a href="./" target="_self">About Re:Learn</a> · '
    '<a href="?view=insights&learner={learner}" target="_self">Insights (for judges and teachers)</a></p>'
)


def render_footer(learner: str) -> None:
    html(INSIGHTS_LINK.format(learner=learner))


def go(screen: str) -> None:
    st.session_state.rl_screen = screen
    st.rerun()


def start_lesson(engine: LessonEngine, learner: str, concept: str | None) -> None:
    seen = st.session_state.setdefault("rl_seen", set())
    st.session_state.rl_flow = engine.start(learner, concept, seen)
    go("lesson")


def render_landing(engine: LessonEngine, tutor: Tutor, learner: str) -> None:
    html(
        '<p class="rl-eyebrow">Re:Learn</p><p class="rl-title">Learn physics by doing</p>'
        '<p class="rl-subtitle">Short interactive questions that help you spot tricky ideas, fix them, '
        "and lock in what you've learned.</p>"
        '<div class="rl-chips"><span class="rl-chip accent">Spot the tricky idea</span>'
        '<span class="rl-chip accent">See it, try it, explain it</span>'
        '<span class="rl-chip accent">Lock it in</span></div>'
    )
    cols = st.columns(2)
    if cols[0].button("Continue learning", key="continue-learning", type="primary", width="stretch"):
        start_lesson(engine, learner, None)
    if cols[1].button("Start guided demo", key="start-demo", width="stretch"):
        st.session_state.rl_flow = start_demo(engine)
        st.session_state.rl_guided = 0
        st.session_state.rl_guided_last = []
        go("guided")
    html('<p class="rl-eyebrow" style="margin-top:1.5rem">Your learning journey</p>')
    html(f'<div class="rl-visual rl-map">{svc.concept_map(tutor, learner)}</div>')
    html('<p class="rl-eyebrow" style="margin-top:1.5rem">Lessons</p>')
    concepts = list(load_content().concepts.values())
    for i in range(0, len(concepts), 2):
        row = st.columns(2)
        for col, concept in zip(row, concepts[i : i + 2], strict=False):
            with col:
                concept_card(
                    concept, svc.concept_status(tutor, learner, concept.id), lambda c: start_lesson(engine, learner, c)
                )


def lesson_actions(engine: LessonEngine, flow: LessonFlow) -> dict:
    def run(fn):
        def inner():
            fn(flow)
            st.rerun()

        return inner

    return {
        "continue": run(engine.continue_),
        "try_again": run(engine.try_again),
        "reveal": run(engine.reveal),
        "try_another": run(engine.try_another),
    }


def render_lesson_body(engine: LessonEngine, flow: LessonFlow, disabled: bool = False) -> None:
    concept = load_content().concepts[flow.concept]
    lesson_header(flow, concept.subtitle)
    progress_indicator(flow)
    if flow.phase == "complete":
        render_complete(engine, flow, disabled)
        return

    def on_check(kind: str, answer: str, working: str) -> None:
        if kind == "quick_check":
            engine.answer_quick_check(flow, answer)
        else:
            engine.check(flow, answer, working)
        st.rerun()

    if flow.phase == "explain":

        def on_explain(text: str) -> None:
            engine.check_explanation(flow, text)
            st.rerun()

        def on_skip() -> None:
            engine.skip_explanation(flow)
            st.rerun()

        explain_card(flow, on_explain, on_skip, disabled)
    else:
        question_card(flow, on_check, disabled)
    answer_feedback(flow, lesson_actions(engine, flow), disabled)


def render_complete(engine: LessonEngine, flow: LessonFlow, disabled: bool) -> None:
    status = svc.concept_status(engine.tutor, flow.learner_id, flow.concept)
    with st.container(key="rl-card-complete"):
        if flow.feedback is not None and flow.feedback.status == "exhausted":
            title = flow.feedback.message
        else:
            title = "Nice work! Lesson complete."
        html(f'<p class="rl-card-name">{title}</p>')
        note = {
            "mastered": "You've mastered this idea.",
            "review": "We've marked this idea to come back to later.",
        }.get(status, "Keep practising to lock this idea in. We'll check back on it in a later lesson.")
        html(f'<p class="rl-card-sub">You worked through {flow.completed} questions. {note}</p>')
        html(f'<div class="rl-visual rl-map">{svc.concept_map(engine.tutor, flow.learner_id)}</div>')
        cols = st.columns(2)
        if cols[0].button(
            "Next suggested lesson", key="next-lesson", type="primary", disabled=disabled, width="stretch"
        ):
            start_lesson(engine, flow.learner_id, None)
        if cols[1].button("All lessons", key="all-lessons", disabled=disabled, width="stretch"):
            go("landing")


def render_lesson(engine: LessonEngine, learner: str) -> None:
    flow = st.session_state.get("rl_flow")
    if flow is None:
        go("landing")
        return
    if st.button("← All lessons", key="back"):
        go("landing")
    render_lesson_body(engine, flow)


def demo_entries(entries: list) -> str:
    if not entries:
        return ""
    rows = "".join(
        f'<li><span class="rl-demo-key">{escape(k)}</span><span class="rl-demo-val">{escape(v)}</span></li>'
        for k, v in entries
    )
    return f'<p class="rl-demo-head">What the student just did</p><ul class="rl-demo-input">{rows}</ul>'


def render_guided(engine: LessonEngine) -> None:
    flow = st.session_state.rl_flow
    index = st.session_state.get("rl_guided", 0)
    done = index >= len(STEPS)
    text = "That's the whole loop. Exit to try it yourself." if done else f"Next: {STEPS[index].label}"
    step = f"Guided demo · step {min(index + 1, len(STEPS))} of {len(STEPS)}"
    html(
        f'<div class="rl-demo" role="status" aria-live="polite"><strong>{step}</strong><br>{text}'
        f"{demo_entries(st.session_state.get('rl_guided_last', []))}</div>"
    )
    cols = st.columns(2)
    if cols[0].button("Next step", key="demo-next", type="primary", disabled=done, width="stretch"):
        st.session_state.rl_guided_last = STEPS[index].action(engine, flow) or []
        st.session_state.rl_guided = index + 1
        st.rerun()
    if cols[1].button("Exit demo", key="demo-exit", width="stretch"):
        st.session_state.pop("rl_flow", None)
        st.session_state.pop("rl_guided_last", None)
        go("landing")
    render_lesson_body(engine, flow, disabled=True)


def render_student(tutor: Tutor, learner: str) -> None:
    inject_theme()
    engine = LessonEngine(tutor)
    screen = st.session_state.get("rl_screen", "landing")
    if tutor.model is None:
        html('<div class="rl-demo">Practice is warming up. Please refresh in a moment.</div>')
    elif screen == "lesson":
        render_lesson(engine, learner)
    elif screen == "guided" and "rl_flow" in st.session_state:
        render_guided(engine)
    else:
        render_landing(engine, tutor, learner)
    render_footer(learner)
