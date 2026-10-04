import streamlit as st
import streamlit.components.v1 as components

from relearn.config import ROOT

LANDING_PATH = ROOT / "docs" / "index.html"
FRAME_CSS = """
<style>
.stApp { background: #0F0D1A; }
[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stSidebarCollapsedControl"] { display: none; }
[data-testid="stMainBlockContainer"] { padding: 0; max-width: none; }
.stApp iframe {
  position: fixed !important; inset: 0; width: 100vw !important; height: 100vh !important;
  border: 0; z-index: 999990; background: #0F0D1A;
}
</style>
"""


def landing_available() -> bool:
    return LANDING_PATH.exists()


def render_landing() -> None:
    st.markdown(FRAME_CSS, unsafe_allow_html=True)
    components.html(LANDING_PATH.read_text(encoding="utf-8"), height=900, scrolling=True)
