from html import escape
from pathlib import Path

from relearn.multimodal.diagrams import load_visuals

JS = Path(__file__).with_name("sim.js")
CSS = Path(__file__).with_name("sim.css")
KINDS = {"slide", "fall", "throw", "collide", "normal", "circle", "energy"}

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><style>{style}</style></head>
<body data-kind="{kind}"><canvas id="sim" width="600" height="260" role="img" aria-label="{caption}"></canvas>
<div id="controls"></div><p id="readout" role="status" aria-live="polite"></p>
<script>{script}</script></body></html>"""


def simulation_spec(misconception: str) -> dict | None:
    return load_visuals().get(misconception, {}).get("simulation")


def simulation_html(misconception: str) -> str | None:
    spec = simulation_spec(misconception)
    if not spec or spec["kind"] not in KINDS:
        return None
    return PAGE.format(
        kind=spec["kind"],
        caption=escape(spec["caption"]),
        style=CSS.read_text(encoding="utf-8"),
        script=JS.read_text(encoding="utf-8"),
    )
