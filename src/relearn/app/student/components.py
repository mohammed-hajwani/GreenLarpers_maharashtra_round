from html import escape
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from relearn import services as svc
from relearn.learning.flow import Feedback, LessonFlow
from relearn.schemas import QuestionType

CSS_PATH = Path(__file__).with_name("theme.css")
ITEM_CHIPS = {"lockin": "One more to lock it in", "review": "Quick review"}
STATUS_TITLES = {
    "correct": ("✓", "correct"),
    "incorrect": ("✗", "incorrect"),
    "incorrect_item": ("✗", "incorrect"),
    "revealed": ("→", "neutral"),
    "needs_more": ("!", "neutral"),
    "deferred": ("↺", "neutral"),
    "exhausted": ("✓", "neutral"),
}
STATUS_CHIPS = {
    "not_started": ("Not started", ""),
    "in_progress": ("In progress", "accent"),
    "mastered": ("Mastered", "mastered"),
    "review": ("Come back to this", "review"),
}


def inject_theme() -> None:
    st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def lesson_header(flow: LessonFlow, subtitle: str) -> None:
    html(
        f'<p class="rl-eyebrow">Lesson</p><p class="rl-title">{escape(flow.concept_name)}</p>'
        f'<p class="rl-subtitle">{escape(subtitle)}</p>'
    )


def progress_indicator(flow: LessonFlow) -> None:
    current, total = flow.progress
    dots = "".join(
        f'<span class="rl-dot {"done" if i < flow.completed else "current" if i == flow.completed else ""}"></span>'
        for i in range(total)
    )
    label = f"Question {current} of {total}"
    html(
        f'<div class="rl-progress" role="progressbar" aria-valuemin="0" aria-valuemax="{total}" '
        f'aria-valuenow="{flow.completed}" aria-label="{label}"><span class="rl-progress-text">{label}</span>'
        f'<span class="rl-dots" aria-hidden="true">{dots}</span></div>'
    )


def item_chip(flow: LessonFlow) -> None:
    kind = flow.item.kind
    if flow.phase == "quick_check":
        html('<span class="rl-chip accent">Quick check</span>')
    elif kind == "lockin":
        done = flow.lockin_total - len(flow.lockin)
        html(f'<span class="rl-chip accent">{ITEM_CHIPS[kind]} · {done} of {flow.lockin_total}</span>')
    elif kind in ITEM_CHIPS:
        html(f'<span class="rl-chip accent">{ITEM_CHIPS[kind]}</span>')


def answer_input(flow: LessonFlow, disabled: bool) -> tuple[str | None, str]:
    question = flow.item.question
    key = f"{question.question_id}-{flow.attempts_on_item}"
    if question.question_type == QuestionType.mcq:
        answer = st.radio("Your answer", question.options, index=None, key=f"ans-{key}", disabled=disabled)
    else:
        answer = st.text_input("Your answer", key=f"ans-{key}", disabled=disabled, placeholder="Type your answer")
    working = ""
    if flow.item.kind == "practice":
        working = st.text_area(
            "Your thinking (a sentence helps us help you)",
            key=f"work-{key}",
            height=90,
            disabled=disabled,
            placeholder="Why do you think so?",
        )
    return answer, working


def question_card(flow: LessonFlow, on_check, disabled: bool = False) -> None:
    with st.container(key="rl-question-card"):
        item_chip(flow)
        if flow.phase == "quick_check":
            probe = flow.pending["choice"].probe
            html(f'<p class="rl-question">{escape(probe.stem)}</p>')
            with st.form(key=f"quick-{probe.probe_id}", border=False):
                choice = st.radio("Pick one", probe.options, index=None, key=f"qc-{probe.probe_id}", disabled=disabled)
                if st.form_submit_button("Check answer", type="primary", disabled=disabled) and choice:
                    on_check("quick_check", choice, "")
            return
        html(f'<p class="rl-question">{escape(flow.item.question.stem)}</p>')
        if flow.phase == "feedback":
            if flow.last_answer:
                html(f'<p class="rl-your-answer">Your answer: <strong>{escape(flow.last_answer)}</strong></p>')
            return
        with st.form(key=f"answer-{flow.item.question.question_id}-{flow.attempts_on_item}", border=False):
            answer, working = answer_input(flow, disabled)
            submitted = st.form_submit_button("Check answer", type="primary", disabled=disabled)
            if submitted:
                if not answer or not str(answer).strip():
                    live_message("Pick or type an answer first.", "needs_more")
                else:
                    on_check("answer", str(answer), working)


def live_message(message: str, status: str, hint: str = "") -> None:
    icon, tone = STATUS_TITLES.get(status, ("•", "neutral"))
    hint_html = f'<p class="rl-hint">{escape(hint)}</p>' if hint else ""
    html(
        f'<div class="rl-feedback {tone}" role="status" aria-live="polite">'
        f'<p class="rl-feedback-title"><span aria-hidden="true">{icon}</span> {escape(message)}</p>{hint_html}</div>'
    )


def explanation_card(feedback: Feedback, show_answer: bool) -> None:
    answer = (
        f'<p class="rl-explain-label">Answer</p><p class="rl-answer-value">{escape(feedback.answer)}</p>'
        if show_answer and feedback.answer
        else ""
    )
    why = (
        f'<p class="rl-explain-label">Why it works</p><p>{escape(feedback.explanation)}</p>'
        if feedback.explanation
        else ""
    )
    if answer or why:
        html(f'<div class="rl-explain">{answer}{why}</div>')


def answer_feedback(flow: LessonFlow, actions: dict, disabled: bool = False) -> None:
    feedback = flow.feedback
    if feedback is None or feedback.status == "quick_check":
        return
    with st.container(key="rl-feedback-card"):
        live_message(feedback.message, feedback.status, feedback.hint)
        if feedback.status == "incorrect" and feedback.modality != "text" and feedback.visual_for:
            visual_card(feedback.modality, feedback.visual_for)
        if feedback.status in ("correct", "revealed", "incorrect_item"):
            explanation_card(feedback, show_answer=feedback.status != "correct")
        lesson_navigation(feedback.status, flow, actions, disabled)


def visual_card(modality: str, mix_up: str) -> None:
    if modality == "diagram":
        svg = svc.diagram(mix_up)
        if svg:
            title, caption = svc.diagram_text(mix_up)
            html(
                f'<div class="rl-visual"><p class="rl-explain-label">Picture it</p>{svg}'
                f'<p class="rl-visual-caption">{escape(caption)}</p></div>'
            )
    elif modality == "simulation":
        page = svc.simulation(mix_up)
        if page:
            html('<p class="rl-explain-label rl-visual-label">Try it yourself</p>')
            components.html(page, height=430, scrolling=False)
            html(f'<p class="rl-visual-caption">{escape(svc.simulation_caption(mix_up))}</p>')


def lesson_navigation(status: str, flow: LessonFlow, actions: dict, disabled: bool) -> None:
    if status == "needs_more":
        return
    buttons = {
        "correct": [("Continue", "continue", "primary")],
        "incorrect": [("Try again", "try_again", "primary"), ("Reveal answer", "reveal", "secondary")],
        "revealed": [
            ("Try another question of this type", "try_another", "primary"),
            ("Continue", "continue", "secondary"),
        ],
        "incorrect_item": [("Continue", "continue", "primary")],
        "deferred": [("Continue", "continue", "primary")],
        "exhausted": [("Continue", "continue", "primary")],
    }.get(status, [])
    cols = st.columns(len(buttons)) if buttons else []
    for col, (label, action, kind) in zip(cols, buttons, strict=True):
        if col.button(label, key=f"nav-{action}", type=kind, disabled=disabled, width="stretch"):
            actions[action]()


def concept_card(concept, status: str, on_start) -> None:
    label, tone = STATUS_CHIPS[status]
    with st.container(key=f"rl-card-{concept.id}"):
        html(
            f'<span class="rl-chip {tone}">{label}</span><p class="rl-card-name">{escape(concept.name)}</p>'
            f'<p class="rl-card-sub">{escape(concept.subtitle)}</p>'
        )
        verb = "Review" if status == "mastered" else "Continue" if status in ("in_progress", "review") else "Start"
        if st.button(f"{verb}: {concept.name}", key=f"start-{concept.id}", width="stretch"):
            on_start(concept.id)
