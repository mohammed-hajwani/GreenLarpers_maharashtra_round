import re
import uuid

import streamlit as st

from relearn import services as svc
from relearn.pipeline import Tutor

LEARNER_ID = re.compile(r"^[a-z0-9-]{3,40}$")


@st.cache_resource
def get_tutor() -> Tutor:
    return svc.create_tutor()


def health() -> None:
    active = svc.active_model()
    st.write("ok")
    st.write(f"model: {active.source}")
    st.stop()


def current_learner() -> str:
    from_url = st.query_params.get("learner", "")
    if from_url and LEARNER_ID.match(from_url):
        st.session_state.learner_id = from_url
    if "learner_id" not in st.session_state:
        st.session_state.learner_id = "learner-" + uuid.uuid4().hex[:8]
    return st.session_state.learner_id


def main() -> None:
    st.set_page_config(page_title="Re:Learn", page_icon="🧲", layout="wide")
    if st.query_params.get("health") == "1":
        health()
    learner = current_learner()
    tutor = get_tutor()
    view = st.query_params.get("view")
    if view == "insights":
        from relearn.app.insights.page import render_insights

        render_insights(tutor, learner)
        return
    from relearn.app.landing import landing_available, render_landing

    if view != "learn" and "learner" not in st.query_params and landing_available():
        render_landing()
        return
    from relearn.app.student.screens import render_student

    render_student(tutor, learner)
