import uuid

import streamlit as st

from relearn.app.demo import load_script, run_demo
from relearn.app.practice import render_practice, reset_flow
from relearn.app.views import render_profile, render_step
from relearn.config import load_config
from relearn.learner.store import LearnerStore
from relearn.models.loader import get_active_model
from relearn.pipeline import Tutor

MODEL_NAMES = {
    "hub_transformer": "DistilBERT (Hugging Face Hub)",
    "baseline": "TF-IDF + logistic regression baseline",
    "unavailable": "no model (demo replay only)",
}


@st.cache_resource
def get_tutor() -> Tutor:
    active = get_active_model()
    return Tutor(LearnerStore(load_config().db_path()), active.model)


def health() -> None:
    active = get_active_model()
    st.write("ok")
    st.write(f"model: {active.source}")
    st.stop()


def demo_page(tutor: Tutor) -> None:
    st.header("Demo mode")
    st.caption(
        "A scripted learner runs through the real pipeline: diagnose → probe → intervene → reassess → retest."
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
        st.warning("Model unavailable: replaying recorded outputs.")
    for step in steps[:idx]:
        with st.container(border=True):
            render_step(step)


def sidebar(tutor: Tutor) -> str:
    with st.sidebar:
        st.title("Re:Learn")
        page = st.radio("Page", ["Practice", "Profile", "Demo mode"])
        st.caption(f"Learner: `{st.session_state.learner_id}`")
        if st.button("Reset demo"):
            tutor.store.reset(st.session_state.learner_id)
            tutor.store.reset(load_script()["learner_id"])
            reset_flow()
            st.session_state.pop("demo_steps", None)
            st.rerun()
        st.divider()
        st.caption(f"Active model: **{MODEL_NAMES[get_active_model().source]}**")
    return page


def main() -> None:
    st.set_page_config(page_title="Re:Learn", page_icon="🧲", layout="wide")
    if st.query_params.get("health") == "1":
        health()
    if "learner_id" not in st.session_state:
        st.session_state.learner_id = "learner-" + uuid.uuid4().hex[:8]
    tutor = get_tutor()
    page = sidebar(tutor)
    learner = st.session_state.learner_id
    if page == "Practice":
        st.header("Practice")
        if tutor.model is None:
            st.error("No diagnosis model could be loaded. Use Demo mode to replay a recorded session.")
        else:
            render_practice(tutor, learner)
    elif page == "Profile":
        st.header("Learner profile")
        render_profile({"rows": tutor.profile(learner), "timeline": tutor.store.timeline(learner)})
    else:
        demo_page(tutor)
    st.divider()
    st.caption("Prototype. All training data is synthetic. Domain: introductory mechanics.")
