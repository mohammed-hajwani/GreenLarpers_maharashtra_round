import uuid

import streamlit as st

from relearn import services as svc
from relearn.app.dashboard import render_dashboard, render_evaluation_page
from relearn.app.demo import load_script, run_demo
from relearn.app.practice import render_practice, reset_flow
from relearn.app.views import render_profile, render_step
from relearn.pipeline import Tutor

MODEL_NAMES = {
    "v1_embedding": "MiniLM embedding hybrid",
    "baseline": "TF-IDF + logistic regression baseline",
    "replay": "no model loaded (labeled replay only)",
}


@st.cache_resource
def get_tutor() -> Tutor:
    return svc.create_tutor()


def health() -> None:
    active = svc.active_model()
    st.write("ok")
    st.write(f"model: {active.source}")
    st.stop()


def demo_page(tutor: Tutor) -> None:
    st.header("Demo mode")
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


BADGE_COLOR = {"v1_embedding": "green", "baseline": "orange", "replay": "red"}


def model_badge() -> None:
    active = svc.active_model()
    version = f" v{active.model.version}" if active.model else ""
    st.markdown(f":{BADGE_COLOR[active.source]}-badge[Active model: {MODEL_NAMES[active.source]}{version}]")


def sidebar(tutor: Tutor) -> str:
    with st.sidebar:
        st.title("Re:Learn")
        page = st.radio("Page", ["Practice", "Dashboard", "Profile", "Model Evaluation", "Demo mode"])
        st.caption(f"Learner: `{st.session_state.learner_id}`")
        if st.button("Reset demo"):
            svc.reset(tutor, st.session_state.learner_id)
            svc.reset(tutor, load_script()["learner_id"])
            reset_flow()
            st.session_state.pop("demo_steps", None)
            st.rerun()
        st.divider()
        st.caption(f"Active model: **{MODEL_NAMES[svc.active_model().source]}**")
    return page


def main() -> None:
    st.set_page_config(page_title="Re:Learn", page_icon="🧲", layout="wide")
    if st.query_params.get("health") == "1":
        health()
    if "learner_id" not in st.session_state:
        st.session_state.learner_id = "learner-" + uuid.uuid4().hex[:8]
    tutor = get_tutor()
    page = sidebar(tutor)
    model_badge()
    learner = st.session_state.learner_id
    if page == "Practice":
        st.header("Practice")
        if tutor.model is None:
            st.error("No diagnosis model could be loaded. Use Demo mode to replay a recorded session.")
        else:
            render_practice(tutor, learner)
    elif page == "Dashboard":
        st.header("Learning analytics")
        who = st.radio("Learner", ["you", "demo learner"], horizontal=True)
        render_dashboard(tutor, learner if who == "you" else load_script()["learner_id"])
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
