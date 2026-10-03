import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

importlib.import_module("relearn.app.streamlit_app").main()
