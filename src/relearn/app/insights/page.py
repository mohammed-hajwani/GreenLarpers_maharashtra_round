import pandas as pd
import streamlit as st

from relearn import services as svc
from relearn.app.demo import load_script, run_demo
from relearn.app.insights.dashboard import render_dashboard, render_evaluation_page
from relearn.app.insights.practice import render_practice, reset_flow
from relearn.app.insights.trace_view import render_assessment_trace, render_practice_trace
from relearn.app.insights.views import render_profile, render_step
from relearn.learning.guided import DEMO_LEARNER
from relearn.pipeline import Tutor

MODEL_NAMES = {
    "v1_embedding": "MiniLM embedding hybrid",
    "baseline": "TF-IDF + logistic regression baseline",
    "replay": "no model loaded (labeled replay only)",
}
BADGE_COLOR = {"v1_embedding": "green", "baseline": "orange", "replay": "red"}
PAGES = ["Student decisions", "AI practice console", "Dashboard", "Profile", "Model Evaluation", "AI demo walkthrough"]


def model_badge() -> None:
    active = svc.active_model()
    version = f" v{active.model.version}" if active.model else ""
    st.markdown(f":{BADGE_COLOR[active.source]}-badge[Active model: {MODEL_NAMES[active.source]}{version}]")


def demo_page(tutor: Tutor) -> None:
    st.header("AI demo walkthrough")
    st.caption(
        "A scripted learner runs through the real pipeline: diagnose → information-gain probe → decision trace → "
        "intervene → reassess (trap) → escalate → reassess → adaptive spacing → delayed retest → dashboard."
    )
    cols = st.columns(3)
    if cols[0].button("Start demo", type="primary"):
        if tutor.model is None:
            st.session_state.demo_steps = load_script()["recorded_steps"]
            st.session_state.demo_replay = True
        else:
            st.session_state.demo_steps = run_demo(tutor)
            st.session_state.demo_replay = False
        st.session_state.demo_idx = 1
    steps = st.session_state.get("demo_steps")
    if not steps:
        return
    idx = st.session_state.get("demo_idx", 1)
    if cols[1].button("Next step", disabled=idx >= len(steps)):
        st.session_state.demo_idx = idx = idx + 1
    if cols[2].button("Show all"):
        st.session_state.demo_idx = idx = len(steps)
    if st.session_state.get("demo_replay"):
        st.error(
            "REPLAY: no model could be loaded, so these are recorded outputs from an earlier real run, "
            "not live inference."
        )
    for step in steps[:idx]:
        with st.container(border=True):
            render_step(step)


def student_decisions(tutor: Tutor, learner: str) -> None:
    st.header("Student decisions")
    st.caption(
        f"Every AI decision behind the student flow for learner `{learner}`, read from the decision-trace store."
    )
    traces = svc.traces(tutor, learner)
    interventions = [e for e in svc.timeline(tutor, learner) if e["kind"] == "intervention"]
    if not traces and not interventions:
        st.info("No decisions recorded for this learner yet. Answer a question in the student view first.")
        return
    for record in reversed(traces):
        title = f"#{record['id']} · {record['kind']} · {record['ts']}"
        with st.container(border=True):
            st.markdown(f"**{title}**")
            if record["kind"] == "practice":
                st.caption(record["question"])
                render_practice_trace(record)
            else:
                render_assessment_trace(record)
    if interventions:
        st.subheader("Hints delivered (intervention strategy and sources)")
        passages = svc.passages_by_id()
        rows = [
            {
                "step": e["ts"],
                "misconception": e["misconception"],
                "strategy": e["ref_id"],
                "mode": e.get("mode", "template"),
                "sources": "; ".join(f"{pid}: {passages.get(pid, '')[:90]}" for pid in e.get("sources", [])),
            }
            for e in interventions
        ]
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def render_insights(tutor: Tutor, learner: str) -> None:
    with st.sidebar:
        st.title("Re:Learn Insights")
        st.caption("For judges and teachers")
        page = st.radio("Page", PAGES)
        st.caption(f"Learner: `{learner}`")
        if st.button("Reset demo"):
            svc.reset(tutor, learner)
            svc.reset(tutor, load_script()["learner_id"])
            reset_flow()
            st.session_state.pop("demo_steps", None)
            st.rerun()
        st.divider()
        st.caption(f"Active model: **{MODEL_NAMES[svc.active_model().source]}**")
        st.markdown(f'<a href="?learner={learner}" target="_self">Back to the student view</a>', unsafe_allow_html=True)
    model_badge()
    if page == "Student decisions":
        who = st.radio("Show decisions for", ["this learner", "guided demo learner"], horizontal=True)
        student_decisions(tutor, learner if who == "this learner" else DEMO_LEARNER)
    elif page == "AI practice console":
        st.header("AI practice console")
        if tutor.model is None:
            st.error("No diagnosis model could be loaded. Use the demo walkthrough to replay a recorded session.")
        else:
            render_practice(tutor, learner)
    elif page == "Dashboard":
        st.header("Learning analytics")
        who = st.radio("Learner", ["this learner", "demo learner"], horizontal=True)
        render_dashboard(tutor, learner if who == "this learner" else load_script()["learner_id"])
    elif page == "Model Evaluation":
        st.header("Model evaluation")
        render_evaluation_page()
    elif page == "Profile":
        st.header("Learner profile")
        render_profile({"rows": svc.profile(tutor, learner), "timeline": svc.timeline(tutor, learner)})
    else:
        demo_page(tutor)
    st.divider()
    st.caption("Prototype. All training data is synthetic. Domain: introductory mechanics.")
