import streamlit as st

from relearn.pipeline import Tutor

INSIGHTS_LINK = (
    '<p class="rl-footer"><a href="?view=insights&learner={learner}" target="_self">'
    "Insights (for judges and teachers)</a></p>"
)


def render_footer(learner: str) -> None:
    st.markdown(INSIGHTS_LINK.format(learner=learner), unsafe_allow_html=True)


def render_student(tutor: Tutor, learner: str) -> None:
    st.title("Re:Learn")
    st.markdown("Learn physics by working through tricky ideas, one question at a time.")
    render_footer(learner)
