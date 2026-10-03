from streamlit.testing.v1 import AppTest

from relearn.config import ROOT

APP_PATH = str(ROOT / "app.py")


def insights_app(page: str | None = None, timeout: int = 180) -> AppTest:
    at = AppTest.from_file(APP_PATH, default_timeout=timeout)
    at.query_params["view"] = "insights"
    at.run()
    if page is not None:
        at.sidebar.radio[0].set_value(page)
        at.run()
    return at
